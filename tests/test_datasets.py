from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from balanceops.datasets import DatasetBundle, DatasetSpec, load_dataset, register_loader


def test_dataset_registry_register_and_load(tmp_path: Path):
    def _loader(spec: DatasetSpec) -> DatasetBundle:
        X = np.ones((3, 2), dtype=float)
        y = np.array([0, 1, 0])
        return DatasetBundle(X=X, y=y, feature_names=["a", "b"], meta={"ok": True})

    register_loader("toy", _loader, overwrite=True)

    spec = DatasetSpec(kind="toy", name="my-toy", params={"x": 1})
    b = load_dataset(spec)

    assert b.X.shape == (3, 2)
    assert b.meta["dataset_kind"] == "toy"
    assert b.meta["dataset_name"] == "my-toy"
    assert isinstance(b.meta.get("dataset_spec"), dict)


def test_csv_loader_basic(tmp_path: Path):
    df = pd.DataFrame(
        {
            "f1": [1.0, 2.0, 3.0],
            "f2": [10.0, 20.0, 30.0],
            "y": [0, 1, 0],
        }
    )
    p = tmp_path / "toy.csv"
    df.to_csv(p, index=False)

    spec = DatasetSpec(kind="csv", params={"path": str(p), "target_col": "y", "one_hot": False})
    b = load_dataset(spec)

    assert b.X.shape == (3, 2)
    assert b.y.shape == (3,)
    assert b.meta["dataset_kind"] == "csv"
    assert b.meta["fingerprint"]["sha256"]


def test_csv_loader_one_hot_and_target_mapping(tmp_path: Path):
    df = pd.DataFrame(
        {
            "color": ["red", "blue", "red"],
            "value": [1, 2, 3],
            "label": ["no", "yes", "no"],
        }
    )
    p = tmp_path / "toy2.csv"
    df.to_csv(p, index=False)

    spec = DatasetSpec(
        kind="csv",
        params={"path": str(p), "target_col": "label", "one_hot": True, "dropna": True},
    )
    b = load_dataset(spec)

    assert set(np.unique(b.y)).issubset({0, 1})
    assert "target_mapping" in b.meta
    assert any("color_" in n for n in (b.feature_names or []))
