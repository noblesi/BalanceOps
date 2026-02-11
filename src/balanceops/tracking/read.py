from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from balanceops.tracking.db import connect


def _safe_json_loads(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _read_manifest_pointer(artifacts_root: Path, run_id: str) -> dict[str, Any] | None:
    p = artifacts_root / "runs" / "_by_id" / f"{run_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_latest_pointer(artifacts_root: Path) -> dict[str, Any] | None:
    p = artifacts_root / "runs" / "_latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _group_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        rid = str(r["run_id"])
        out.setdefault(rid, {})[str(r["key"])] = float(r["value"])
    return out


def list_runs_summary(
    db_path: str,
    *,
    limit: int = 20,
    offset: int = 0,
    include_metrics: bool = True,
    artifacts_root: str | Path | None = None,
    include_run_dir_name: bool = False,
) -> list[dict[str, Any]]:
    """최근 run 요약 목록.

    - include_run_dir_name=True이고 artifacts_root가 주어지면,
      artifacts/runs/_by_id/<run_id>.json 포인터에서 run_dir_name을 함께 로드합니다.
      (대시보드에서 사람이 읽기 쉬운 run 라벨 표시에 사용)
    """
    con = connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        SELECT run_id, created_at, git_commit, git_branch, git_dirty, params_json, note
        FROM runs
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (int(limit), int(offset)),
    )
    run_rows = [dict(r) for r in cur.fetchall()]

    metrics_map: dict[str, dict[str, float]] = {}
    if include_metrics and run_rows:
        run_ids = [r["run_id"] for r in run_rows]
        placeholders = ",".join(["?"] * len(run_ids))
        cur.execute(
            f"SELECT run_id, key, value FROM metrics WHERE run_id IN ({placeholders})",
            run_ids,
        )
        metrics_map = _group_metrics([dict(r) for r in cur.fetchall()])

    con.close()

    ar: Path | None = None
    if include_run_dir_name and artifacts_root is not None:
        ar = Path(artifacts_root)

    out: list[dict[str, Any]] = []
    for r in run_rows:
        rid = str(r["run_id"])

        params = _safe_json_loads(r.get("params_json"))
        kind = params.get("kind") if isinstance(params, dict) else None

        item: dict[str, Any] = {
            "run_id": rid,
            "created_at": r["created_at"],
            "git": {
                "commit": r.get("git_commit"),
                "branch": r.get("git_branch"),
                "dirty": bool(r.get("git_dirty")),
            },
            "note": r.get("note"),
            "kind": kind,
        }

        if include_metrics:
            item["metrics"] = metrics_map.get(rid, {})

        if ar is not None:
            p = _read_manifest_pointer(ar, rid)
            if p and isinstance(p.get("run_dir_name"), str):
                item["run_dir_name"] = p["run_dir_name"]

        out.append(item)
    return out


def get_run_detail(
    db_path: str,
    *,
    run_id: str,
    artifacts_root: str | Path | None = None,
) -> dict[str, Any] | None:
    """run_id 단건 상세(Params/Metrics/Artifacts/Manifest 포인터 포함)."""
    con = connect(db_path)
    cur = con.cursor()
    cur.execute(
        """
        SELECT run_id, created_at, git_commit, git_branch, git_dirty, params_json, note
        FROM runs
        WHERE run_id = ?
        """,
        (run_id,),
    )
    row = cur.fetchone()
    if row is None:
        con.close()
        return None

    run_row = dict(row)

    cur.execute("SELECT key, value FROM metrics WHERE run_id = ? ORDER BY key", (run_id,))
    metrics = {str(r["key"]): float(r["value"]) for r in cur.fetchall()}

    cur.execute("SELECT kind, path FROM artifacts WHERE run_id = ? ORDER BY kind, path", (run_id,))
    artifacts = [{"kind": str(r["kind"]), "path": str(r["path"])} for r in cur.fetchall()]

    con.close()

    params = _safe_json_loads(run_row.get("params_json"))

    detail: dict[str, Any] = {
        "run_id": run_row["run_id"],
        "created_at": run_row["created_at"],
        "git": {
            "commit": run_row.get("git_commit"),
            "branch": run_row.get("git_branch"),
            "dirty": bool(run_row.get("git_dirty")),
        },
        "note": run_row.get("note"),
        "params": params if isinstance(params, dict) else None,
        "metrics": metrics,
        "artifacts": artifacts,
    }

    if artifacts_root is not None:
        ar = Path(artifacts_root)
        detail["manifest"] = _read_manifest_pointer(ar, run_id)

    return detail


def get_latest_run_id(
    *, artifacts_root: str | Path | None = None, db_path: str | None = None
) -> str | None:
    """가능하면 artifacts/runs/_latest.json을 사용하고, 없으면 DB의 최신 created_at을 사용."""
    if artifacts_root is not None:
        p = _read_latest_pointer(Path(artifacts_root))
        if p and isinstance(p.get("run_id"), str):
            return p["run_id"]

    if db_path is None:
        return None

    con = connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    con.close()
    return str(row["run_id"]) if row else None
