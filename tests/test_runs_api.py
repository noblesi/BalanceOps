import os
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from balanceops.pipeline.demo_run import main as demo_main
from balanceops.tracking.init_db import init_db


def _set_env(tmp_path: Path) -> None:
    os.environ["BALANCEOPS_DB"] = str(tmp_path / "balanceops.db")
    os.environ["BALANCEOPS_ARTIFACTS"] = str(tmp_path / "artifacts")
    os.environ["BALANCEOPS_CURRENT_MODEL"] = str(
        tmp_path / "artifacts" / "models" / "current.joblib"
    )


def test_runs_endpoints_smoke(tmp_path: Path):
    _set_env(tmp_path)
    init_db(str(tmp_path / "balanceops.db"))
    demo_main()

    client = TestClient(app)

    r = client.get("/runs", params={"limit": 10, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert isinstance(data["items"], list)

    run_id = data["items"][0]["run_id"]

    r2 = client.get(f"/runs/{run_id}")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["run_id"] == run_id
    assert isinstance(d2.get("metrics"), dict)
    assert d2.get("params") is None or isinstance(d2.get("params"), dict)
    assert d2.get("manifest") is None or isinstance(d2.get("manifest"), dict)

    r3 = client.get("/runs/latest")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["run_id"] == run_id


def test_run_not_found_returns_404(tmp_path: Path):
    _set_env(tmp_path)
    init_db(str(tmp_path / "balanceops.db"))

    client = TestClient(app)
    r = client.get("/runs/not-a-run-id")
    assert r.status_code == 404
