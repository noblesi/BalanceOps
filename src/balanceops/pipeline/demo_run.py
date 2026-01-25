from __future__ import annotations

import uuid
from pathlib import Path

from balanceops.common.config import get_settings
from balanceops.tracking.log_run import create_run, log_metric
from balanceops.tracking.manifest import write_run_manifest


def main() -> None:
    s = get_settings()
    run_id = str(uuid.uuid4())
    params = {"kind": "demo", "seed": 42}

    create_run(s.db_path, run_id=run_id, params=params, note="demo run for wiring check")
    log_metric(s.db_path, run_id, "acc", 0.90)
    log_metric(s.db_path, run_id, "bal_acc", 0.88)

    manifest_path = write_run_manifest(
        run_id=run_id,
        kind="demo",
        status="success",
        artifacts_root=Path(s.artifacts_dir),
        db_path=Path(s.db_path),
        metrics={"acc": 0.90, "bal_acc": 0.88},
    )

    print(f"[OK] manifest written: {manifest_path}")
    print(f"[OK] demo run inserted: {run_id}")


if __name__ == "__main__":
    main()
