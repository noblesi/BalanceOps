from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class HttpResult:
    ok: bool
    status_code: int | None
    content: str | None
    obj: Any | None
    error: str | None


def _format_obj(obj: Any | None, content: str | None) -> str:
    if obj is not None:
        try:
            return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return str(obj)
    return (content or "").strip()


def _request_json(
    client: httpx.Client,
    *,
    method: str,
    url: str,
    body: Any | None = None,
) -> HttpResult:
    try:
        resp = client.request(method, url, json=body, headers={"Accept": "application/json"})
    except Exception as e:
        # NOTE: 일부 환경(특히 Windows/로컬)에서는 connect 단계의 예외가 httpx.HTTPError로
        # 래핑되지 않고 그대로 올라오는 케이스가 있다.
        # E2E/스모크에서 "서버 아직 안 뜸" 상황을 재시도로 흡수하기 위해 broad catch.
        return HttpResult(
            ok=False,
            status_code=None,
            content=None,
            obj=None,
            error=f"{type(e).__name__}: {e}",
        )
    content: str | None = None
    obj: Any | None = None
    try:
        content = resp.text
        if content and content.strip():
            try:
                obj = resp.json()
            except Exception:
                obj = content
    except Exception as e:
        return HttpResult(
            ok=False,
            status_code=resp.status_code,
            content=None,
            obj=None,
            error=f"failed to read response: {e}",
        )

    ok = 200 <= resp.status_code < 300
    return HttpResult(ok=ok, status_code=resp.status_code, content=content, obj=obj, error=None)


def _with_retry(
    *,
    name: str,
    action: Callable[[], HttpResult],
    retries: int,
    retry_delay_sec: float,
    no_retry_codes: set[int],
) -> HttpResult:
    max_attempts = max(1, retries + 1)
    last: HttpResult | None = None

    for attempt in range(1, max_attempts + 1):
        res = action()
        last = res

        if res.ok:
            return res

        if res.status_code is not None and res.status_code in no_retry_codes:
            return res

        if attempt >= max_attempts:
            return res

        code_text = f"HTTP {res.status_code}" if res.status_code is not None else "no-status"
        err_text = res.error or "request failed"
        warn = (
            f"[smoke] WARN {name} attempt {attempt}/{max_attempts} failed "
            f"({code_text}): {err_text}. "
            f"retry in {retry_delay_sec}s"
        )
        print(warn, file=sys.stderr)
        time.sleep(max(0.0, retry_delay_sec))

    return last or HttpResult(
        ok=False,
        status_code=None,
        content=None,
        obj=None,
        error="null response",
    )


def run(
    *,
    base_url: str,
    timeout_sec: float,
    retries: int,
    retry_delay_sec: float,
    health_path: str,
    predict_path: str,
    features: list[float],
    skip_predict: bool,
    allow_predict_failure: bool,
    fail_on_predict_404: bool,
) -> int:
    base_url = base_url.rstrip("/")
    if not health_path.startswith("/"):
        health_path = "/" + health_path
    if not predict_path.startswith("/"):
        predict_path = "/" + predict_path

    print(f"[smoke] base_url: {base_url}")
    print(
        "[smoke] timeout_sec: "
        f"{timeout_sec}, retries: {retries}, retry_delay_sec: {retry_delay_sec}"
    )

    with httpx.Client(timeout=timeout_sec) as client:
        # 1) /health
        health = _with_retry(
            name=f"GET {health_path}",
            action=lambda: _request_json(client, method="GET", url=f"{base_url}{health_path}"),
            retries=retries,
            retry_delay_sec=retry_delay_sec,
            no_retry_codes={404},
        )

        if not health.ok:
            code_text = (
                f"HTTP {health.status_code}" if health.status_code is not None else "no-status"
            )
            err_text = health.error or "request failed"
            print(f"[smoke] {health_path} FAILED ({code_text}): {err_text}", file=sys.stderr)
            return 1

        print(
            f"[smoke] {health_path} OK (HTTP {health.status_code}): "
            f"{_format_obj(health.obj, health.content)}"
        )

        if skip_predict:
            print("[smoke] skip predict.")
            print("[smoke] done.")
            return 0

        # 2) /predict
        payload = {"features": features}
        pred = _with_retry(
            name=f"POST {predict_path}",
            action=lambda: _request_json(
                client, method="POST", url=f"{base_url}{predict_path}", body=payload
            ),
            retries=retries,
            retry_delay_sec=retry_delay_sec,
            no_retry_codes={404},
        )

        if pred.ok:
            print(
                f"[smoke] {predict_path} OK (HTTP {pred.status_code}): "
                f"{_format_obj(pred.obj, pred.content)}"
            )
            print("[smoke] done.")
            return 0

        if pred.status_code == 404:
            msg = f"[smoke] {predict_path} returned 404 (current model missing?)"
            if fail_on_predict_404:
                print(msg, file=sys.stderr)
                return 1
            print(f"[smoke] WARN {msg}", file=sys.stderr)
            return 0

        code_text = f"HTTP {pred.status_code}" if pred.status_code is not None else "no-status"
        err_text = pred.error or "request failed"
        err_msg = f"[smoke] {predict_path} FAILED ({code_text}): {err_text}"

        if allow_predict_failure:
            print(f"[smoke] WARN {err_msg}", file=sys.stderr)
            return 0

        print(err_msg, file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="HTTP smoke check for BalanceOps API endpoints.")

    # target
    ap.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="base URL like http://127.0.0.1:8000 (overrides --host/--port)",
    )
    ap.add_argument("--host", type=str, default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)

    # timing
    ap.add_argument("--timeout-sec", type=float, default=10)
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--retry-delay-sec", type=float, default=0.5)

    # endpoints
    ap.add_argument("--health-path", type=str, default="/health")
    ap.add_argument("--predict-path", type=str, default="/predict")

    # payload
    ap.add_argument(
        "--features",
        type=float,
        nargs="+",
        default=[0.1, 0.2, -0.3, 1.0, 0.5, 0.0, -0.2, 0.9],
        help="features array for POST /predict",
    )

    # behavior
    ap.add_argument("--skip-predict", action="store_true")
    ap.add_argument("--allow-predict-failure", action="store_true")
    ap.add_argument("--fail-on-predict-404", action="store_true")

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    base_url = args.base_url
    if not base_url:
        base_url = f"http://{args.host}:{args.port}"

    return run(
        base_url=base_url,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        retry_delay_sec=args.retry_delay_sec,
        health_path=args.health_path,
        predict_path=args.predict_path,
        features=list(args.features),
        skip_predict=bool(args.skip_predict),
        allow_predict_failure=bool(args.allow_predict_failure),
        fail_on_predict_404=bool(args.fail_on_predict_404),
    )


if __name__ == "__main__":
    raise SystemExit(main())
