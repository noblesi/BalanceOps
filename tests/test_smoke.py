import os
from pathlib import Path

from balanceops.tracking.init_db import init_db
from balanceops.pipeline.demo_run import main as demo_main
from balanceops.registry.current import load_current_model


def test_smoke(tmp_path: Path):
    db = tmp_path / "balanceops.db"
    os.environ["BALANCEOPS_DB"] = str(db)
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(tmp_path / "artifacts" / "models" / "current.joblib")

    init_db(str(db))
    demo_main()

    assert db.exists()

def test_load_current_model_none_when_no_row(tmp_path: Path):
    """DB에 current row가 없을 때도 예외 없이 None을 반환해야 한다."""
    db = tmp_path / "balanceops.db"
    os.environ["BALANCEOPS_DB"] = str(db)
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(tmp_path / "artifacts" / "models" / "current.joblib")

    init_db(str(db))

    model = load_current_model()
    assert model is None

def test_imports():
    import balanceops
    import pandas
    import streamlit
