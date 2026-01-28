import json
import os
from pathlib import Path

from balanceops.pipeline.train_dummy import train_dummy_run
from balanceops.tracking.db import connect
from balanceops.tracking.init_db import init_db


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def _upsert_current_model_row(db_path: Path, metrics: dict) -> None:
    con = connect(str(db_path))
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
        (
            "balance_model",
            "seed-current",
            str(db_path.parent / "artifacts" / "models" / "current.joblib"),
            "2026-01-01T00:00:00+00:00",
            json.dumps(metrics, ensure_ascii=False),
        ),
    )
    con.commit()
    con.close()


def test_train_dummy_uses_current_metrics_when_present(tmp_path: Path) -> None:
    """current row가 있을 때 'no current model yet'로 오판하지 않아야 한다."""
    _set_env(tmp_path)
    db = tmp_path / "balanceops.db"
    init_db(str(db))

    # 정책상 절대 개선 불가능한 값으로 current를 심어 deterministic 하게 만든다.
    _upsert_current_model_row(db, {"bal_acc": 100.0, "recall_1": 100.0})

    out = train_dummy_run(seed=42, n_samples=200, n_features=8, auto_promote=True)

    assert out["promoted"] is False
    assert out["reason"] != "no current model yet"
    assert "not enough improvement" in out["reason"]
