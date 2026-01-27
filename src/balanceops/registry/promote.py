from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from balanceops.common.config import get_settings
from balanceops.tracking.db import connect


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def promote_run(
    run_id: str, model_path: str, metrics: dict | None = None, name: str = "balance_model"
) -> str:
    s = get_settings()

    src = Path(model_path)
    if not src.exists():
        raise FileNotFoundError(f"model_path not found: {src}")

    dst = Path(s.current_model_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    con = connect(s.db_path)
    con.execute(
        """
        INSERT INTO models(name, stage, run_id, path, created_at, metrics_json)
        VALUES (?, 'current', ?, ?, ?, ?)
        ON CONFLICT(name, stage) DO UPDATE SET
          run_id=excluded.run_id,
          path=excluded.path,
          created_at=excluded.created_at,
          metrics_json=excluded.metrics_json
        """,
        (name, run_id, str(dst), utc_now_iso(), json.dumps(metrics or {}, ensure_ascii=False)),
    )
    con.commit()
    con.close()
    return str(dst)
