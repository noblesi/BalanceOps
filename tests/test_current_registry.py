from __future__ import annotations

import os
from pathlib import Path

import joblib

import balanceops.registry.current as cur


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def test_get_current_model_info_closes_connection(monkeypatch, tmp_path: Path):
    _set_env(tmp_path)

    class FakeCon:
        def __init__(self):
            self.closed = False

        def execute(self, _sql: str, _params: tuple):
            class FakeCursor:
                def fetchone(self_inner):
                    return {
                        "name": "balance_model",
                        "stage": "current",
                        "run_id": "r1",
                        "path": "artifacts/models/current.joblib",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "metrics_json": "{}",
                    }

            return FakeCursor()

        def close(self):
            self.closed = True

    fake_con = FakeCon()

    def fake_connect(_db_path: str):
        return fake_con

    monkeypatch.setattr(cur, "connect", fake_connect)

    info = cur.get_current_model_info()
    assert info["run_id"] == "r1"
    assert fake_con.closed is True


def test_load_current_model_falls_back_to_settings_path(monkeypatch, tmp_path: Path):
    _set_env(tmp_path)

    # settings.current_model_path 위치에 실제 파일 생성
    p = tmp_path / "artifacts" / "models" / "current.joblib"
    p.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"ok": True}, p)

    # DB path는 존재하지 않는 걸로 반환 → fallback 타야 함
    monkeypatch.setattr(
        cur, "get_current_model_info", lambda name="balance_model": {"path": "missing.joblib"}
    )

    m = cur.load_current_model()
    assert m == {"ok": True}
