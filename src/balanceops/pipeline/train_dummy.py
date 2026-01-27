from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

import joblib
import numpy as np

from balanceops.common.config import get_settings
from balanceops.models.dummy import DummyBalanceModel
from balanceops.registry.current import get_current_model_info
from balanceops.registry.policy import should_promote
from balanceops.registry.promote import promote_run
from balanceops.tracking.log_run import create_run, log_artifact, log_metric
from balanceops.tracking.manifest import write_run_manifest


def _metrics_from_synth(
    model: DummyBalanceModel, n_samples: int, n_features: int, seed: int
) -> dict:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n_samples, n_features))
    p = model.predict_proba(x)[:, 1]
    y = rng.binomial(1, p)

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


def train_dummy_run(
    *, seed: int = 42, n_samples: int = 300, n_features: int = 8, auto_promote: bool = True
) -> dict:
    s = get_settings()
    run_id = str(uuid.uuid4())

    rng = np.random.default_rng(seed)
    model = DummyBalanceModel(seed=seed, w=rng.normal(size=(n_features,)), b=float(rng.normal()))

    # run 기록
    params = {"kind": "train_dummy", "seed": seed, "n_samples": n_samples, "n_features": n_features}
    create_run(s.db_path, run_id=run_id, params=params, note="dummy model training for E2E check")

    metrics = _metrics_from_synth(model, n_samples=n_samples, n_features=n_features, seed=seed)
    for k, v in metrics.items():
        log_metric(s.db_path, run_id, k, v)

    # candidate 모델 저장
    candidates_dir = Path(s.artifacts_dir) / "models" / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = candidates_dir / f"{run_id}_dummy.joblib"
    joblib.dump(model, candidate_path)
    log_artifact(s.db_path, run_id, "model_candidate", str(candidate_path))

    # manifest
    manifest_path = write_run_manifest(
        run_id=run_id,
        kind="train_dummy",
        status="success",
        artifacts_root=Path(s.artifacts_dir),
        db_path=Path(s.db_path),
        metrics=metrics,
    )

    promoted = False
    decision_reason = "auto_promote disabled"
    if auto_promote:
        cur = get_current_model_info()
        cur_metrics = None
        if cur.get("exists"):
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
        "metrics": metrics,
        "promoted": promoted,
        "reason": decision_reason,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-samples", type=int, default=300)
    ap.add_argument("--n-features", type=int, default=8)
    ap.add_argument("--no-auto-promote", action="store_true")
    args = ap.parse_args()

    out = train_dummy_run(
        seed=args.seed,
        n_samples=args.n_samples,
        n_features=args.n_features,
        auto_promote=not args.no_auto_promote,
    )

    print(f"[OK] run_id: {out['run_id']}")
    print(f"[OK] candidate: {out['candidate_path']}")
    print(f"[OK] manifest: {out['manifest_path']}")
    print(f"[OK] promoted: {out['promoted']} ({out['reason']})")
    print(f"[OK] metrics: {out['metrics']}")


if __name__ == "__main__":
    main()
