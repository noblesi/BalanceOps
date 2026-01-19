from __future__ import annotations

import uuid

from balanceops.common.config import get_settings
from balanceops.tracking.log_run import create_run, log_metric


def main() -> None:
    s = get_settings()
    run_id = str(uuid.uuid4())
    params = {"kind": "demo", "seed": 42}
    create_run(s.db_path, run_id=run_id, params=params, note="demo run for wiring check")
    log_metric(s.db_path, run_id, "acc", 0.90)
    log_metric(s.db_path, run_id, "bal_acc", 0.88)
    print(f"[OK] demo run inserted: {run_id}")


if __name__ == "__main__":
    main()
