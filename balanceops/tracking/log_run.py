from __future__ import annotations

import json
from datetime import datetime, timezone

from balanceops.common.gitinfo import get_git_info
from balanceops.tracking.db import connect


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_run(db_path: str, run_id: str, params: dict, note: str | None = None) -> None:
    gi = get_git_info()
    con = connect(db_path)
    con.execute(
        """
        INSERT INTO runs(run_id, created_at, git_commit, git_branch, git_dirty, params_json, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            utc_now_iso(),
            gi.commit,
            gi.branch,
            1 if gi.dirty else 0,
            json.dumps(params, ensure_ascii=False),
            note,
        ),
    )
    con.commit()
    con.close()


def log_metric(db_path: str, run_id: str, key: str, value: float) -> None:
    con = connect(db_path)
    con.execute(
        """
        INSERT INTO metrics(run_id, key, value) VALUES (?, ?, ?)
        ON CONFLICT(run_id, key) DO UPDATE SET value=excluded.value
        """,
        (run_id, key, float(value)),
    )
    con.commit()
    con.close()


def log_artifact(db_path: str, run_id: str, kind: str, path: str) -> None:
    con = connect(db_path)
    con.execute(
        "INSERT INTO artifacts(run_id, kind, path) VALUES (?, ?, ?)",
        (run_id, kind, path),
    )
    con.commit()
    con.close()
