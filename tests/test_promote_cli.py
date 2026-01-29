from __future__ import annotations

import os
from pathlib import Path

import joblib
import numpy as np

from balanceops.models.dummy import DummyBalanceModel
from balanceops.registry.promote_cli import main as promote_main
from balanceops.tracking.db import connect
from balanceops.tracking.init_db import init_db
from balanceops.tracking.log_run import create_run, log_artifact, log_metric


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def test_promote_cli_promotes_candidate_by_run_id(tmp_path: Path):
    _set_env(tmp_path)
    db = tmp_path / "balanceops.db"
    init_db(str(db))

    run_id = "r1"
    create_run(str(db), run_id=run_id, params={"kind": "test"}, note="test promote cli")
    log_metric(str(db), run_id, "acc", 0.9)

    cand_dir = tmp_path / "artifacts" / "models" / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    cand_path = cand_dir / f"{run_id}_dummy.joblib"

    m = DummyBalanceModel(seed=1, w=np.zeros(8, dtype=float), b=1.0)
    joblib.dump(m, cand_path)

    log_artifact(str(db), run_id, "model_candidate", str(cand_path))

    code = promote_main(["--run-id", run_id])
    assert code == 0

    current_path = tmp_path / "artifacts" / "models" / "current.joblib"
    assert current_path.exists()

    con = connect(str(db))
    row = con.execute(
        "SELECT run_id, path FROM models WHERE name='balance_model' AND stage='current'"
    ).fetchone()
    con.close()

    assert row is not None
    assert row["run_id"] == run_id
