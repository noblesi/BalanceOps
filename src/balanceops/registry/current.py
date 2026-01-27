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

    row = con.execute(sql, (name,)).fetchone()

    if row is None:
        return {}

    return {
        "name": row[0],
        "stage": row[1],
        "run_id": row[2],
        "path": row[3],
        "created_at": row[4],
        "metrics_json": row[5],
    }


def load_current_model(name: str = "balance_model"):
    info = get_current_model_info(name=name)
    if not info:
        return None

    path = info.get("path")
    if not path:
        return None

    p = Path(path)
    if not p.exists():
        # path가 상대경로로 저장된 경우를 대비(선택)
        # 여기서 artifacts_root까지 합치고 싶으면 settings를 이용해 확장 가능
        return None

    return joblib.load(p)
