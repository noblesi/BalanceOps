import os
from pathlib import Path

from balanceops.tracking.init_db import init_db
from balanceops.pipeline.demo_run import main as demo_main


def test_smoke(tmp_path: Path):
    db = tmp_path / "balanceops.db"
    os.environ["BALANCEOPS_DB"] = str(db)
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(tmp_path / "artifacts" / "models" / "current.joblib")

    init_db(str(db))
    demo_main()

    assert db.exists()
