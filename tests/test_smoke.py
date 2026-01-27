import json
import os
import re
from pathlib import Path

from balanceops.pipeline.demo_run import main as demo_main
from balanceops.registry.current import load_current_model
from balanceops.tracking.init_db import init_db


def test_smoke(tmp_path: Path):
    db = tmp_path / "balanceops.db"
    os.environ["BALANCEOPS_DB"] = str(db)
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )

    init_db(str(db))
    demo_main()

    latest = tmp_path / "artifacts" / "runs" / "_latest.json"
    assert latest.exists()

    info = json.loads(latest.read_text(encoding="utf-8"))
    assert re.match(r"^\d{8}_\d{6}_demo_[0-9A-Za-z]{8}$", info["run_dir_name"])

    assert db.exists()


def test_load_current_model_none_when_no_row(tmp_path: Path):
    """DB에 current row가 없을 때도 예외 없이 None을 반환해야 한다."""
    db = tmp_path / "balanceops.db"
    os.environ["BALANCEOPS_DB"] = str(db)
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )

    init_db(str(db))

    model = load_current_model()
    assert model is None


def test_imports():
    pass
