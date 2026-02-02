from __future__ import annotations

import argparse
import sys
from pathlib import Path

from balanceops.common.config import get_settings
from balanceops.registry.promote import promote_run
from balanceops.tracking.read import get_latest_run_id, get_run_detail


def _pick_model_path(artifacts: list[dict]) -> str | None:
    # train_dummy가 쓰는 kind 우선
    preferred = ["model_candidate", "model_current", "model"]
    for k in preferred:
        for a in artifacts:
            if str(a.get("kind")) == k and a.get("path"):
                return str(a["path"])
    # 그래도 없으면 첫 번째 artifact라도
    if artifacts:
        p = artifacts[0].get("path")
        return str(p) if p else None
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Promote a run's model to current.")
    g = ap.add_mutually_exclusive_group(required=False)
    g.add_argument("--run-id", type=str, default=None, help="target run_id")
    g.add_argument("--latest", action="store_true", help="use latest run_id")
    ap.add_argument("--model-path", type=str, default=None, help="override model path (optional)")
    ap.add_argument(
        "--name", type=str, default="balance_model", help="model name (default: balance_model)"
    )
    args = ap.parse_args(argv)

    s = get_settings()

    run_id = args.run_id
    if args.latest:
        run_id = get_latest_run_id(artifacts_root=s.artifacts_dir, db_path=s.db_path)

    if not run_id:
        ap.error("either --run-id or --latest is required")

    detail = get_run_detail(s.db_path, run_id=run_id)
    if detail is None:
        print(f"[ERR] run_id not found: {run_id}", file=sys.stderr)
        return 2

    metrics = detail.get("metrics") or {}
    artifacts = detail.get("artifacts") or []

    model_path = args.model_path or _pick_model_path(artifacts)
    if not model_path:
        print(f"[ERR] no model artifact found for run_id: {run_id}", file=sys.stderr)
        return 3

    # 경로 표시용 정리(상대/절대 상관 없이 promote_run에서 존재 체크)
    model_path = str(Path(model_path))

    try:
        dst = promote_run(run_id=run_id, model_path=model_path, metrics=metrics, name=args.name)
    except FileNotFoundError as e:
        print(f"[ERR] {e}", file=sys.stderr)
        return 4

    print(f"[OK] promoted run_id={run_id} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
