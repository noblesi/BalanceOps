from __future__ import annotations

from balanceops.common.config import get_settings
from balanceops.tracking.db import connect


DDL = [
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        git_commit TEXT,
        git_branch TEXT,
        git_dirty INTEGER,
        params_json TEXT,
        note TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS metrics (
        run_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value REAL NOT NULL,
        PRIMARY KEY (run_id, key)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        run_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        path TEXT NOT NULL
    );
    """,
    # Model registry: name="balance_model", stage in {"candidate","current","archived"}
    """
    CREATE TABLE IF NOT EXISTS models (
        name TEXT NOT NULL,
        stage TEXT NOT NULL,
        run_id TEXT,
        path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        metrics_json TEXT,
        PRIMARY KEY (name, stage)
    );
    """,
]


def init_db(db_path: str) -> None:
    con = connect(db_path)
    cur = con.cursor()
    for q in DDL:
        cur.execute(q)
    con.commit()
    con.close()


def main() -> None:
    s = get_settings()
    init_db(s.db_path)
    print(f"[OK] initialized DB: {s.db_path}")


if __name__ == "__main__":
    main()
