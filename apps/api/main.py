from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from balanceops.common.config import get_settings
from balanceops.common.version import get_build_info
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_latest_run_id, get_run_detail, list_runs_summary


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # startup
    s = get_settings()
    init_db(s.db_path)
    yield
    # shutdown: 필요하면 정리 작업


app = FastAPI(lifespan=lifespan)


class PredictRequest(BaseModel):
    features: list[float]


def _err(
    code: str,
    message: str,
    *,
    hint: str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if hint:
        err["hint"] = hint
    if details is not None:
        err["details"] = details
    return err


def _error_response(request: Request, status_code: int, err: dict[str, Any]) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload: dict[str, Any] = {"ok": False, "error": err}
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=payload)


def _infer_expected_n_features(model: Any) -> int | None:
    # 1) sklearn 계열: Pipeline/Estimator가 n_features_in_ 제공하는 경우
    v = getattr(model, "n_features_in_", None)
    if isinstance(v, int) and v > 0:
        return v

    # 2) Pipeline 내부 step에서 찾기(StandardScaler 등)
    steps = getattr(model, "named_steps", None)
    if isinstance(steps, dict):
        for step in steps.values():
            vv = getattr(step, "n_features_in_", None)
            if isinstance(vv, int) and vv > 0:
                return vv

    # 3) 커스텀 모델이 제공할 수 있는 힌트
    v2 = getattr(model, "expected_n_features", None)
    if isinstance(v2, int) and v2 > 0:
        return v2

    return None


@app.middleware("http")
async def _request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    resp = await call_next(request)
    resp.headers["X-Request-ID"] = rid
    return resp


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        err = exc.detail
    else:
        err = _err("HTTP_ERROR", str(exc.detail))
    return _error_response(request, exc.status_code, err)


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    err = _err("VALIDATION_ERROR", "Invalid request.", details=exc.errors())
    return _error_response(request, 422, err)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # 내부 예외 메시지를 그대로 노출하지 않음(세부는 type만 제공)
    err = _err("INTERNAL_ERROR", "Unexpected server error.", details={"type": type(exc).__name__})
    return _error_response(request, 500, err)


@dataclass
class _HotModelCache:
    db_path: str | None = None
    run_id: str | None = None
    path: str | None = None
    mtime_ns: int | None = None
    model: Any | None = None


_MODEL_LOCK = Lock()
_MODEL_CACHE = _HotModelCache()


def _unwrap_loaded_model(obj: Any) -> Any:
    # train_tabular_baseline에서 dict 래퍼로 저장한 모델 호환
    if isinstance(obj, dict) and "model" in obj:
        return obj["model"]
    return obj


def _clear_model_cache() -> None:
    with _MODEL_LOCK:
        _MODEL_CACHE.db_path = None
        _MODEL_CACHE.run_id = None
        _MODEL_CACHE.path = None
        _MODEL_CACHE.mtime_ns = None
        _MODEL_CACHE.model = None


def _resolve_model_path(path: str) -> Path:
    """DB에 저장된 path를 가능한 한 실제 파일 경로로 해석."""
    p = Path(path)
    if p.exists():
        return p

    # 상대경로인 경우 artifacts_dir 하위도 한 번 더 시도
    if not p.is_absolute():
        s = get_settings()
        p2 = Path(s.artifacts_dir) / p
        if p2.exists():
            return p2

    return p


def _get_model():
    """현재(current) 모델을 캐시하되, 파일 변경(mtime)
    DB current 포인터 변경 시 자동으로 재로딩."""
    db_path = get_settings().db_path
    info = get_current_model_info()
    if not info:
        _clear_model_cache()
        return None

    path = info.get("path")
    if not path:
        _clear_model_cache()
        return None

    p = _resolve_model_path(str(path))
    try:
        mtime_ns = p.stat().st_mtime_ns
    except FileNotFoundError:
        # DB의 path가 다른 OS/환경의 절대경로로 저장되어 있어 깨진 경우,
        # canonical 경로(settings.current_model_path)를 한 번 더 시도한다.
        fallback = Path(get_settings().current_model_path)
        try:
            mtime_ns = fallback.stat().st_mtime_ns
            p = fallback
        except FileNotFoundError:
            _clear_model_cache()
            return None

    run_id = info.get("run_id")

    with _MODEL_LOCK:
        if (
            _MODEL_CACHE.model is not None
            and _MODEL_CACHE.db_path == db_path
            and _MODEL_CACHE.path == str(p)
            and _MODEL_CACHE.run_id == run_id
            and _MODEL_CACHE.mtime_ns == mtime_ns
        ):
            return _MODEL_CACHE.model

    raw = joblib.load(p)
    model = _unwrap_loaded_model(raw)

    # predict_proba 계약 체크(더 친절한 에러)
    if not hasattr(model, "predict_proba"):
        raise RuntimeError(
            f"current model does not support predict_proba (loaded_type={type(raw).__name__})"
        )

    with _MODEL_LOCK:
        _MODEL_CACHE.db_path = db_path
        _MODEL_CACHE.model = model
        _MODEL_CACHE.path = str(p)
        _MODEL_CACHE.run_id = run_id
        _MODEL_CACHE.mtime_ns = mtime_ns

    return model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, Any]:
    """서버 식별용 버전/빌드 정보.

    - 대시보드/운영에서 "이 서버가 어떤 커밋으로 떠 있는지" 확인하는 용도.
    - 추가: 현재 모델이 기대하는 feature 개수(expected_n_features)
    """
    info: dict[str, Any] = {
        "service": "balanceops-api",
        **get_build_info(),
    }

    # 모델이 없거나 로딩 실패해도 /version은 살아있게
    try:
        model = _get_model()  # predict에서 쓰는 동일 로더/캐시 사용
        info["expected_n_features"] = _infer_expected_n_features(model) or 8
        info["model_type"] = type(model).__name__
    except Exception as e:
        info["expected_n_features"] = None
        info["model_type"] = None
        info["model_error"] = str(e)

    return info


@app.get("/model")
def model_info() -> dict[str, Any]:
    return get_current_model_info()


@app.get("/runs")
def list_runs(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    include_metrics: bool = True,
) -> dict[str, Any]:
    s = get_settings()
    items = list_runs_summary(
        s.db_path,
        limit=limit,
        offset=offset,
        include_metrics=include_metrics,
        artifacts_root=s.artifacts_dir,
        include_run_dir_name=True,
    )
    return {"items": items, "limit": limit, "offset": offset, "count": len(items)}


@app.get("/runs/latest")
def latest_run() -> dict[str, Any]:
    s = get_settings()
    run_id = get_latest_run_id(artifacts_root=s.artifacts_dir, db_path=s.db_path)
    if run_id is None:
        raise HTTPException(
            status_code=404,
            detail=_err(
                "RUN_NOT_FOUND",
                "No runs found.",
                hint=(
                    "Run scripts/run_once.ps1 "
                    "(or: python -m balanceops.pipeline.demo_run) "
                    "to create one."
                ),
            ),
        )

    detail = get_run_detail(s.db_path, run_id=run_id, artifacts_root=s.artifacts_dir)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=_err(
                "RUN_NOT_FOUND",
                "Run not found.",
                details={"run_id": run_id},
            ),
        )
    return detail


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    s = get_settings()
    detail = get_run_detail(s.db_path, run_id=run_id, artifacts_root=s.artifacts_dir)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=_err(
                "RUN_NOT_FOUND",
                "Run not found.",
                details={"run_id": run_id},
            ),
        )
    return detail


@app.post("/predict")
def predict(req: PredictRequest):
    try:
        model = _get_model()
    except Exception as e:
        _clear_model_cache()
        raise HTTPException(
            status_code=500,
            detail=_err(
                "CURRENT_MODEL_LOAD_FAILED",
                "Failed to load current model.",
                hint="Re-promote a valid model as current.",
                details={"type": type(e).__name__, "message": str(e)},
            ),
        )

    if model is None:
        raise HTTPException(
            status_code=404,
            detail=_err(
                "NO_CURRENT_MODEL",
                "No current model promoted yet.",
                hint=(
                    "Run scripts/train_dummy.ps1 "
                    "(or: python -m balanceops.pipeline.train_dummy) "
                    "to promote one."
                ),
            ),
        )

    expected = _infer_expected_n_features(model) or 8  # 힌트가 없으면 기존 계약(8)로 fallback
    got = len(req.features)

    if expected != got:
        raise HTTPException(
            status_code=400,
            detail=_err(
                "FEATURE_SIZE_MISMATCH",
                "Feature length mismatch.",
                hint="Call GET /version and send features with expected_n_features length.",
                details={
                    "expected_n_features": expected,
                    "got_n_features": got,
                },
            ),
        )

    proba = model.predict_proba([req.features])[0][1]
    return {"p_win": float(proba)}
