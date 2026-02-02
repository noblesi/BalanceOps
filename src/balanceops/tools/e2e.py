"""Cross-platform E2E one-shot runner.

This tool is intended to be used locally or in CI as a single command to validate
that BalanceOps is "good enough to run":

1) init_db
2) (optional) train dummy model (+ auto-promote attempt)
3) ensure current model exists (fallback: promote latest)
4) start API server (uvicorn) in background
5) smoke check /health and /predict
6) stop server

Usage:
  python -m balanceops.tools.e2e
  python -m balanceops.tools.e2e --port 8010
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from balanceops.common.config import get_settings
from balanceops.pipeline.train_dummy import train_dummy_run
from balanceops.registry.current import load_current_model
from balanceops.registry.promote_cli import main as promote_main
from balanceops.tools.smoke_http import run as smoke_run
from balanceops.tracking.init_db import init_db


def _find_repo_root(start: Path) -> Path:
    """Try to locate repo root even when executed outside of repo root."""
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() and (p / "src").exists() and (p / "apps").exists():
            return p
    return start


def _with_repo_pythonpath(env: dict[str, str], repo_root: Path) -> dict[str, str]:
    """Ensure apps/ and src/ are importable for uvicorn subprocess."""
    sep = os.pathsep
    existing = env.get("PYTHONPATH", "")
    parts = [str(repo_root), str(repo_root / "src")]
    if existing.strip():
        parts.append(existing)
    env["PYTHONPATH"] = sep.join(parts)
    return env


def _start_server(*, repo_root: Path, host: str, port: int) -> subprocess.Popen:
    env = _with_repo_pythonpath(os.environ.copy(), repo_root)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    print(f"[e2e] starting api: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=env,
    )

    time.sleep(0.2)
    if proc.poll() is not None:
        raise RuntimeError(
            f"api server exited immediately (exitcode={proc.returncode}). Is the port in use?"
        )

    return proc


def _stop_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return

    print(f"[e2e] stopping api server (pid={proc.pid})")
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="BalanceOps E2E one-shot runner.")

    ap.add_argument("--host", type=str, default="127.0.0.1", help="bind host for uvicorn")
    ap.add_argument("--port", type=int, default=8000, help="bind port for uvicorn")

    ap.add_argument("--timeout-sec", type=float, default=8)
    ap.add_argument("--retries", type=int, default=30)
    ap.add_argument("--retry-delay-sec", type=float, default=0.5)

    ap.add_argument("--skip-train", action="store_true", help="skip dummy training")
    ap.add_argument("--skip-serve", action="store_true", help="skip serve+smoke")

    return ap


def run_e2e(
    *,
    host: str,
    port: int,
    timeout_sec: float,
    retries: int,
    retry_delay_sec: float,
    skip_train: bool,
    skip_serve: bool,
) -> int:
    repo_root = _find_repo_root(Path.cwd())
    print(f"[e2e] repo_root: {repo_root}")
    print(f"[e2e] host: {host}  port: {port}")

    s = get_settings()

    print("[e2e] step 1/4: init_db")
    init_db(s.db_path)
    print(f"[e2e] db OK: {s.db_path}")

    if not skip_train:
        print("[e2e] step 2/4: train_dummy (auto-promote)")
        out = train_dummy_run(auto_promote=True)
        print(
            "[e2e] train_dummy: "
            f"run_id={out['run_id']} promoted={out['promoted']} reason={out['reason']}"
        )
    else:
        print("[e2e] step 2/4: skip train_dummy")

    print("[e2e] step 3/4: ensure current model")
    cur = load_current_model()
    if cur is None:
        print("[e2e] current model missing. trying manual promote of latest run...")
        code = promote_main(["--latest"])
        if code != 0:
            print(f"[e2e] promote_cli failed (exitcode={code})", file=sys.stderr)
            return 1
        cur = load_current_model()

    if cur is None:
        print(
            "[e2e] current model still missing. Run 'python -m balanceops.pipeline.train_dummy' "
            "or 'python -m balanceops.registry.promote_cli --latest'",
            file=sys.stderr,
        )
        return 1

    cur_path = Path(s.current_model_path)
    if not cur_path.exists():
        print(f"[e2e] WARN settings.current_model_path does not exist: {cur_path}")
    else:
        print(f"[e2e] current model OK: {cur_path}")

    if skip_serve:
        print("[e2e] step 4/4: skip serve+smoke")
        print("[e2e] done.")
        return 0

    print("[e2e] step 4/4: serve (background) + smoke_http")
    server_proc: subprocess.Popen | None = None
    try:
        server_proc = _start_server(repo_root=repo_root, host=host, port=port)

        code = smoke_run(
            base_url=f"http://{host}:{port}",
            timeout_sec=timeout_sec,
            retries=retries,
            retry_delay_sec=retry_delay_sec,
            health_path="/health",
            predict_path="/predict",
            features=[0.1, 0.2, -0.3, 1.0, 0.5, 0.0, -0.2, 0.9],
            skip_predict=False,
            allow_predict_failure=False,
            fail_on_predict_404=True,
        )
        if code != 0:
            print(f"[e2e] smoke_http failed (exitcode={code})", file=sys.stderr)
            return code

        print("[e2e] OK")
        return 0
    finally:
        if server_proc is not None:
            _stop_server(server_proc)


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)

    return run_e2e(
        host=args.host,
        port=args.port,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        retry_delay_sec=args.retry_delay_sec,
        skip_train=bool(args.skip_train),
        skip_serve=bool(args.skip_serve),
    )


if __name__ == "__main__":
    raise SystemExit(main())
