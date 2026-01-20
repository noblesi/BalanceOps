from __future__ import annotations

import joblib

from balanceops.common.config import get_settings
from balanceops.tracking.db import connect


def get_current_model_info(name: str = "balance_model") -> dict:
    s = get_settings()
    con = connect(s.db_path)
    row = con.execute(
        "SELECT name, stage, run_id, path, created_at, metrics_json FROM models WHERE name=? AND stage='current'",
        (name,),
    ).fetchone()
    con.close()
    if row is None:
        return {"exists": False, "name": name}
    return {
        "exists": True,
        "name": row["name"],
        "stage": row["stage"],
        "run_id": row["run_id"],
        "path": row["path"],
        "created_at": row["created_at"],
        "metrics_json": row["metrics_json"],
    }


def load_current_model(name: str = "balance_model"):
    info = get_current_model_info(name=name)
    if not info.get("exists"):
        return None
    return joblib.load(info["path"])
