from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from balanceops.datasets.bundle import DatasetBundle
from balanceops.datasets.fingerprint import sha256_file
from balanceops.datasets.registry import DatasetSpec, register_loader


def _bool(v: Any, default: bool) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return default


def load_csv_dataset(spec: DatasetSpec) -> DatasetBundle:
    """CSV 파일을 DatasetBundle로 로드.

    spec.params 지원 키:
      - path (required)
      - target_col (required)
      - feature_cols (optional)
      - one_hot (default: True)
      - dropna (default: True)
      - sep (default: ',')
      - encoding (optional)
    """
    params = spec.params
    path = params.get("path")
    target_col = params.get("target_col")
    if not path:
        raise ValueError("csv loader requires params.path")
    if not target_col:
        raise ValueError("csv loader requires params.target_col")

    p = Path(str(path))
    if not p.exists():
        raise FileNotFoundError(str(p))

    sep = str(params.get("sep") or ",")
    encoding = params.get("encoding")
    one_hot = _bool(params.get("one_hot"), True)
    dropna = _bool(params.get("dropna"), True)

    df = pd.read_csv(p, sep=sep, encoding=encoding)
    if target_col not in df.columns:
        raise ValueError(f"target_col not found: {target_col}")

    feature_cols = params.get("feature_cols")
    if feature_cols is None:
        x_df = df.drop(columns=[target_col])
    else:
        cols = list(feature_cols)
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"feature_cols not found: {missing}")
        x_df = df[cols]

    y = df[target_col]

    if dropna:
        mask = ~(x_df.isna().any(axis=1) | y.isna())
        x_df = x_df.loc[mask]
        y = y.loc[mask]

    if one_hot:
        x_df = pd.get_dummies(x_df, drop_first=False)

    # y: non-numeric이면 "이진"만 지원(0/1 매핑 기록)
    if y.dtype == bool:
        y_arr = y.astype(int).to_numpy()
        target_mapping = {"False": 0, "True": 1}
    elif pd.api.types.is_numeric_dtype(y.dtype):
        y_arr = y.to_numpy()
        target_mapping = None
    else:
        uniq = list(pd.unique(y))
        if len(uniq) != 2:
            raise ValueError(
                "csv loader currently supports binary target only when target is non-numeric"
            )
        uniq_sorted = sorted([str(u) for u in uniq])
        mapping = {uniq_sorted[0]: 0, uniq_sorted[1]: 1}
        y_arr = y.astype(str).map(mapping).to_numpy()
        target_mapping = mapping

    X = x_df.to_numpy(dtype=float)
    feature_names = [str(c) for c in x_df.columns]

    meta: dict[str, Any] = {
        "source": {"type": "csv", "path": str(p)},
        "fingerprint": {"sha256": sha256_file(p)},
        "target_col": str(target_col),
        "feature_cols": [str(c) for c in x_df.columns],
        "n_rows": int(X.shape[0]),
        "n_features": int(X.shape[1]),
    }
    if target_mapping is not None:
        meta["target_mapping"] = target_mapping

    return DatasetBundle(X=X, y=y_arr, feature_names=feature_names, meta=meta)


# built-in
register_loader("csv", load_csv_dataset, overwrite=True)
