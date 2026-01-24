from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    run_dir_name: str
    created_at: str
    kind: str
    status: str
    artifacts_dir: str
    db_path: str
    metrics: Dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(s: str) -> str:
    """Filesystem-safe short slug."""
    s = s.strip()
    s = re.sub(r"[^0-9A-Za-z]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "run"


def _default_run_dir_name(*, run_id: str, kind: str, created_dt: datetime) -> str:
    # 예: 20260124_163015_train_dummy_2fef9e39
    ts = created_dt.strftime("%Y%m%d_%H%M%S")  # UTC 기준(원하면 KST로 바꿀 수 있음)
    short = re.sub(r"[^0-9A-Za-z]", "", run_id)[:8] or run_id[:8]
    return f"{ts}_{_slug(kind)}_{short}"


def _write_by_id_pointer(
    *,
    artifacts_root: Path,
    run_id: str,
    run_dir_name: str,
    manifest_path: Path,
    created_at: str,
) -> None:
    """run_id -> manifest 경로 포인터(폴더명이 UUID가 아니어도 쉽게 찾기 위함)."""
    by_id_dir = artifacts_root / "runs" / "_by_id"
    by_id_dir.mkdir(parents=True, exist_ok=True)
    p = by_id_dir / f"{run_id}.json"
    p.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_dir_name": run_dir_name,
                "manifest_path": manifest_path.as_posix(),
                "created_at": created_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_run_manifest(
    *,
    run_id: str,
    kind: str,
    status: str,
    artifacts_root: Path = Path("artifacts"),
    db_path: Path | None = None,
    metrics: Optional[Dict[str, Any]] = None,
    write_latest: bool = True,
    run_dir_name: str | None = None,
) -> Path:
    """
    - run_id(UUID)는 DB/레지스트리 식별자로 유지
    - 폴더명은 사람이 읽기 쉬운 run_dir_name(기본: YYYYMMDD_HHMMSS_kind_shortid)
    - run_id로도 찾기 쉽도록 artifacts/runs/_by_id/<run_id>.json 포인터 기록
    """
    db_path = db_path or (Path("data") / "balanceops.db")
    if not isinstance(db_path, Path):
        db_path = Path(db_path)

    metrics = metrics or {}

    created_dt = _utc_now()
    created_at = created_dt.isoformat()

    if run_dir_name is None:
        run_dir_name = _default_run_dir_name(run_id=run_id, kind=kind, created_dt=created_dt)

    run_dir = artifacts_root / "runs" / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = RunManifest(
        run_id=run_id,
        run_dir_name=run_dir_name,
        created_at=created_at,
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

    _write_by_id_pointer(
        artifacts_root=artifacts_root,
        run_id=run_id,
        run_dir_name=run_dir_name,
        manifest_path=manifest_path,
        created_at=created_at,
    )

    if write_latest:
        latest_path = artifacts_root / "runs" / "_latest.json"
        latest_path.parent.mkdir(parents=True, exist_ok=True)
        latest_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "run_dir_name": run_dir_name,
                    "manifest_path": manifest_path.as_posix(),
                    "created_at": created_at,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return manifest_path
