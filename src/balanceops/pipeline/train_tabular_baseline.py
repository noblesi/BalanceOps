from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from balanceops.common.config import get_settings
from balanceops.datasets import DatasetSpec, load_dataset
from balanceops.registry.current import get_current_model_info
from balanceops.registry.policy import should_promote
from balanceops.registry.promote import promote_run
from balanceops.tracking.init_db import init_db
from balanceops.tracking.log_run import create_run, log_artifact, log_metric
from balanceops.tracking.manifest import write_run_manifest


def _require_sklearn() -> tuple[Any, Any, Any]:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return LogisticRegression, train_test_split, Pipeline, StandardScaler
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "scikit-learn이 필요합니다. (pip install scikit-learn)\n"
            "프로젝트 기준으로는 requirements.txt 설치가 가장 확실합니다."
        ) from e


def _binary_metrics(y_true: np.ndarray, y_proba: np.ndarray) -> dict[str, float]:
    y = np.asarray(y_true).astype(int)
    p = np.asarray(y_proba).astype(float)

    yhat = (p >= 0.5).astype(int)

    tp = int(((y == 1) & (yhat == 1)).sum())
    tn = int(((y == 0) & (yhat == 0)).sum())
    fp = int(((y == 0) & (yhat == 1)).sum())
    fn = int(((y == 1) & (yhat == 0)).sum())

    acc = (tp + tn) / max(1, (tp + tn + fp + fn))
    tpr = tp / max(1, (tp + fn))  # recall_1
    tnr = tn / max(1, (tn + fp))
    bal_acc = 0.5 * (tpr + tnr)

    return {"acc": float(acc), "bal_acc": float(bal_acc), "recall_1": float(tpr)}


def train_tabular_baseline_run(
    *,
    dataset: DatasetSpec,
    seed: int = 42,
    test_size: float = 0.2,
    auto_promote: bool = True,
) -> dict[str, Any]:
    LogisticRegression, train_test_split, Pipeline, StandardScaler = _require_sklearn()

    s = get_settings()
    init_db(s.db_path)

    run_id = str(uuid.uuid4())

    # 1) dataset load
    bundle = load_dataset(dataset)
    X = np.asarray(bundle.X, dtype=float)
    y = np.asarray(bundle.y).astype(int)

    if X.ndim != 2:
        raise ValueError(f"X must be 2D array, got shape={X.shape}")
    if y.ndim != 1:
        raise ValueError(f"y must be 1D array, got shape={y.shape}")
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X/y size mismatch: {X.shape[0]} vs {y.shape[0]}")

    uniq = set(np.unique(y).tolist())
    if not uniq.issubset({0, 1}):
        raise ValueError(f"binary target required (0/1). got={sorted(uniq)}")

    # 2) split
    X_tr, X_te, y_tr, y_te = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=seed,
        stratify=y if len(uniq) == 2 else None,
    )

    # 3) train baseline (scaler + logistic)
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    random_state=seed,
                    solver="lbfgs",
                ),
            ),
        ]
    )
    model.fit(X_tr, y_tr)

    # 4) eval
    proba = model.predict_proba(X_te)[:, 1]
    metrics = _binary_metrics(y_te, proba)

    # 5) run 기록
    params = {
        "kind": "train_tabular_baseline",
        "seed": seed,
        "test_size": test_size,
        "dataset": dataset.to_dict(),
        "dataset_meta": {
            "dataset_kind": bundle.meta.get("dataset_kind"),
            "dataset_name": bundle.meta.get("dataset_name"),
            "fingerprint": bundle.meta.get("fingerprint"),
        },
        "shape": {"n_samples": int(X.shape[0]), "n_features": int(X.shape[1])},
    }
    create_run(s.db_path, run_id=run_id, params=params, note="tabular baseline training")

    for k, v in metrics.items():
        log_metric(s.db_path, run_id, k, v)

    # 6) candidate 모델 저장
    candidates_dir = Path(s.artifacts_dir) / "models" / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = candidates_dir / f"{run_id}_tabular_baseline.joblib"
    joblib.dump(
        {
            "model": model,
            "feature_names": bundle.feature_names,
            "dataset_meta": bundle.meta,
        },
        candidate_path,
    )
    log_artifact(s.db_path, run_id, "model_candidate", str(candidate_path))

    # 7) manifest
    manifest_path = write_run_manifest(
        run_id=run_id,
        kind="train_tabular_baseline",
        status="success",
        artifacts_root=Path(s.artifacts_dir),
        db_path=Path(s.db_path),
        metrics=metrics,
    )

    # 8) dataset meta artifact (run dir)
    run_dir = manifest_path.parent
    dataset_meta_path = run_dir / "dataset.json"
    dataset_meta_path.write_text(
        json.dumps(
            {
                "dataset_spec": dataset.to_dict(),
                "feature_names": bundle.feature_names,
                "meta": bundle.meta,
                "shape": {"n_samples": int(X.shape[0]), "n_features": int(X.shape[1])},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log_artifact(s.db_path, run_id, "dataset_meta", str(dataset_meta_path))

    # 9) auto-promote
    promoted = False
    decision_reason = "auto_promote disabled"
    if auto_promote:
        cur = get_current_model_info()
        cur_metrics = None
        if cur:
            try:
                cur_metrics = json.loads(cur.get("metrics_json") or "{}")
            except Exception:
                cur_metrics = None

        decision = should_promote(metrics, cur_metrics)
        decision_reason = decision.reason
        if decision.should_promote:
            dst = promote_run(run_id=run_id, model_path=str(candidate_path), metrics=metrics)
            log_artifact(s.db_path, run_id, "model_current", dst)
            promoted = True

    return {
        "run_id": run_id,
        "candidate_path": str(candidate_path),
        "manifest_path": str(manifest_path),
        "dataset_meta_path": str(dataset_meta_path),
        "metrics": metrics,
        "promoted": promoted,
        "reason": decision_reason,
    }


def _spec_from_args(args: argparse.Namespace) -> DatasetSpec:
    if args.dataset_spec:
        return DatasetSpec.from_json(args.dataset_spec)

    if not args.csv_path or not args.target_col:
        raise ValueError("either --dataset-spec OR (--csv-path and --target-col) is required")

    return DatasetSpec(
        kind="csv",
        name=args.dataset_name,
        params={
            "path": args.csv_path,
            "target_col": args.target_col,
            "one_hot": (not args.no_one_hot),
            "dropna": (not args.no_dropna),
            "sep": args.sep,
        },
        split={},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-spec", type=str, default=None, help="dataset spec JSON path")
    ap.add_argument("--dataset-name", type=str, default=None)

    ap.add_argument("--csv-path", type=str, default=None)
    ap.add_argument("--target-col", type=str, default=None)
    ap.add_argument("--sep", type=str, default=",")
    ap.add_argument("--no-one-hot", action="store_true")
    ap.add_argument("--no-dropna", action="store_true")

    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--no-auto-promote", action="store_true")

    args = ap.parse_args()

    spec = _spec_from_args(args)
    out = train_tabular_baseline_run(
        dataset=spec,
        seed=args.seed,
        test_size=args.test_size,
        auto_promote=not args.no_auto_promote,
    )

    print(f"[OK] run_id: {out['run_id']}")
    print(f"[OK] candidate: {out['candidate_path']}")
    print(f"[OK] manifest: {out['manifest_path']}")
    print(f"[OK] dataset_meta: {out['dataset_meta_path']}")
    print(f"[OK] promoted: {out['promoted']} ({out['reason']})")
    print(f"[OK] metrics: {out['metrics']}")


if __name__ == "__main__":
    main()
