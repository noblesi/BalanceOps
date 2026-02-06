from __future__ import annotations

import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from balanceops.common.version import get_build_info


def _load_api_app() -> Any:
    """apps/api/main.py를 파일 경로로 로드해서 FastAPI app을 가져온다.

    - apps/가 패키지(__init__.py)여부에 의존하지 않도록 함
    - 테스트 환경에서 import 캐시 충돌을 피하려고 모듈명을 유니크하게 사용
    """
    repo_root = Path(__file__).resolve().parents[1]
    main_py = repo_root / "apps" / "api" / "main.py"
    assert main_py.exists(), f"not found: {main_py}"

    module_name = f"_balanceops_api_main_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, main_py)
    assert spec and spec.loader, "failed to create module spec"

    mod = module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # lifespan에서 init_db를 호출하므로, 테스트용 DB 경로를 tmp로 지정
    monkeypatch.setenv("BALANCEOPS_DB", str(tmp_path / "balanceops.db"))
    monkeypatch.setenv("BALANCEOPS_ARTIFACTS", str(tmp_path / "artifacts"))
    monkeypatch.setenv("BALANCEOPS_CURRENT_MODEL", str(tmp_path / "models" / "current.joblib"))

    app = _load_api_app()
    return TestClient(app)


def test_version_endpoint_min_schema(client: TestClient):
    res = client.get("/version")
    assert res.status_code == 200

    data = res.json()
    assert isinstance(data, dict)

    # ✅ 최소 계약: service는 항상 존재하고, 고정된 값이어야 함
    assert data.get("service") == "balanceops-api"

    # ✅ 최소 계약: get_build_info()가 제공하는 키는 /version에 포함되어야 함
    build = get_build_info()
    assert isinstance(build, dict)

    for k in build.keys():
        assert k in data, f"missing build key in /version response: {k}"
