from __future__ import annotations

from pathlib import Path
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


def load_current_model():
    info = get_current_model_info()
    
    # (A) DB에 current row 자체가 없을 때
    if not info.get("exists", False):
        return None
    
    # (B) DB에는 있는데 path가 비정상(방어)
    path_str = info.get("path")
    if not path_str:
        return None
    
    path = Path(path_str)

    if not path.exists():
        return None  # ✅ 파일 없으면 None

    return joblib.load(str(path))
