from __future__ import annotations

from pathlib import Path

import joblib

from balanceops.common.config import get_settings
from balanceops.tracking.db import connect


def get_current_model_info(name: str = "balance_model") -> dict:
    s = get_settings()
    con = connect(s.db_path)

    sql = (
        "SELECT name, stage, run_id, path, created_at, metrics_json "
        "FROM models WHERE name=? AND stage='current'"
    )

    try:
        row = con.execute(sql, (name,)).fetchone()
        if row is None:
            return {}

        return {
            "name": row["name"],
            "stage": row["stage"],
            "run_id": row["run_id"],
            "path": row["path"],
            "created_at": row["created_at"],
            "metrics_json": row["metrics_json"],
        }
    finally:
        con.close()


def load_current_model(name: str = "balance_model"):
    """DB current row의 path를 우선 사용하고, 실패하면 settings.current_model_path로 fallback."""
    s = get_settings()
    info = get_current_model_info(name=name)
    if not info:
        return None

    path = info.get("path")
    if not path:
        return None

    candidates: list[Path] = []

    p = Path(path)
    candidates.append(p)

    # DB에 상대경로가 저장되거나, CWD가 달라서 못 찾는 경우를 대비
    candidates.append(Path(s.current_model_path))

    for cp in candidates:
        if cp.exists():
            return joblib.load(cp)

    return None
