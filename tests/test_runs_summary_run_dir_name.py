from __future__ import annotations

from pathlib import Path

from balanceops.tracking.init_db import init_db
from balanceops.tracking.log_run import create_run
from balanceops.tracking.manifest import write_run_manifest
from balanceops.tracking.read import list_runs_summary


def test_list_runs_summary_includes_run_dir_name_when_requested(tmp_path: Path) -> None:
    db = tmp_path / "balanceops.db"
    artifacts_root = tmp_path / "artifacts"

    init_db(str(db))

    run_id = "r1"
    create_run(str(db), run_id=run_id, params={"kind": "demo"}, note="test run dir name")

    write_run_manifest(
        run_id=run_id,
        kind="demo",
        status="success",
        artifacts_root=artifacts_root,
        db_path=db,
        metrics={"acc": 0.1},
    )

    items = list_runs_summary(
        str(db),
        limit=10,
        offset=0,
        include_metrics=False,
        artifacts_root=artifacts_root,
        include_run_dir_name=True,
    )

    assert items, "expected at least one run"
    assert isinstance(items[0].get("run_dir_name"), str)
    assert "demo" in items[0]["run_dir_name"]
