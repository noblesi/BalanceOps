# src/balanceops/tracking/manifest.py
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    created_at: str
    kind: str
    status: str
    artifacts_dir: str
    db_path: str
    metrics: Dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_run_manifest(
    *,
    run_id: str,
    kind: str,
    status: str,
    artifacts_root: Path = Path("artifacts"),
    db_path: Path | None = None,
    metrics: Optional[Dict[str, Any]] = None,
    write_latest: bool = True,
) -> Path:
    if not isinstance(db_path, Path):
        db_path = Path(db_path)

    metrics = metrics or {}
    db_path = db_path or (Path("data") / "balanceops.db")

    run_dir = artifacts_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=run_id,
        created_at=_utc_now_iso(),
        kind=kind,
        status=status,
        artifacts_dir=run_dir.as_posix(),
        db_path=db_path.as_posix(),
        metrics=metrics,
    )

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if write_latest:
        latest_path = artifacts_root / "runs" / "_latest.json"
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "manifest_path": manifest_path.as_posix(),
                    "created_at": manifest.created_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return manifest_path
