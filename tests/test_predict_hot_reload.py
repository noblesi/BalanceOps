from __future__ import annotations

import os
from pathlib import Path

import joblib
import numpy as np
from fastapi.testclient import TestClient

from balanceops.models.dummy import DummyBalanceModel
from balanceops.tracking.db import connect
from balanceops.tracking.init_db import init_db


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def _upsert_current_row(db_path: str, *, run_id: str, path: str) -> None:
    con = connect(db_path)
    con.execute(
        """
        INSERT INTO models(name, stage, run_id, path, created_at, metrics_json)
        VALUES ('balance_model', 'current', ?, ?, '2026-01-01T00:00:00+00:00', '{}')
        ON CONFLICT(name, stage) DO UPDATE SET
          run_id=excluded.run_id,
          path=excluded.path,
          created_at=excluded.created_at,
          metrics_json=excluded.metrics_json
        """,
        (run_id, path),
    )
    con.commit()
    con.close()


def test_predict_hot_reload_when_current_model_file_changes(tmp_path: Path):
    _set_env(tmp_path)
    db = tmp_path / "balanceops.db"
    init_db(str(db))

    model_path = tmp_path / "artifacts" / "models" / "current.joblib"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) current 모델(0.5 근처) 저장 + DB current row upsert
    m1 = DummyBalanceModel(seed=1, w=np.zeros(8, dtype=float), b=0.0)
    joblib.dump(m1, model_path)
    _upsert_current_row(str(db), run_id="r1", path=str(model_path))

    # apps.api.main 은 다른 테스트에서 이미 import 되었을 수 있으므로 reload로 캐시 초기화
    import importlib
    import apps.api.main as api_main

    importlib.reload(api_main)

    with TestClient(api_main.app) as client:
        r1 = client.post("/predict", json={"features": [0.0] * 8})
        assert r1.status_code == 200
        p1 = r1.json()["p_win"]
        assert 0.49 < p1 < 0.51

        # 2) 동일 파일을 다른 모델로 덮어쓰기(확률 ~ 1)
        m2 = DummyBalanceModel(seed=2, w=np.zeros(8, dtype=float), b=10.0)
        joblib.dump(m2, model_path)

        # 파일 시스템 mtime 반영을 확실히 하기 위해 utime 호출
        os.utime(model_path, None)

        r2 = client.post("/predict", json={"features": [0.0] * 8})
        assert r2.status_code == 200
        p2 = r2.json()["p_win"]
        assert p2 > 0.99
