import os
from pathlib import Path

import pandas as pd

from balanceops.datasets import DatasetSpec
from balanceops.pipeline.train_tabular_baseline import train_tabular_baseline_run
from balanceops.tracking.init_db import init_db


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def test_train_tabular_baseline_on_csv(tmp_path: Path) -> None:
    _set_env(tmp_path)
    init_db(str(tmp_path / "balanceops.db"))

    df = pd.DataFrame(
        {
            "f1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "f2": [10.0, 9.0, 8.0, 7.0, 6.0, 5.0],
            "y": [0, 0, 0, 1, 1, 1],
        }
    )
    p = tmp_path / "toy.csv"
    df.to_csv(p, index=False)

    spec = DatasetSpec(kind="csv", params={"path": str(p), "target_col": "y", "one_hot": False})
    out = train_tabular_baseline_run(dataset=spec, seed=42, test_size=0.33, auto_promote=True)

    assert Path(out["candidate_path"]).exists()
    assert Path(out["manifest_path"]).exists()
    assert Path(out["dataset_meta_path"]).exists()
    assert set(out["metrics"].keys()) >= {"acc", "bal_acc", "recall_1"}
    assert out["promoted"] is True
    assert Path(os.environ["BALANCEOPS_CURRENT_MODEL"]).exists()
