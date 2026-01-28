from __future__ import annotations

import uuid
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
from balanceops.registry.current import get_current_model_info
from balanceops.tracking.init_db import init_db
from balanceops.tracking.read import get_latest_run_id, get_run_detail, list_runs_summary


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: 여기에서 기존 on_event("startup") 로 하던 작업 수행
    s = get_settings()
    init_db(s.db_path)
    yield
    # shutdown: 필요하면 정리 작업(없으면 비워둬도 됨)


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
    run_id: str | None = None
    path: str | None = None
    mtime_ns: int | None = None
    model: Any | None = None


_MODEL_LOCK = Lock()
_MODEL_CACHE = _HotModelCache()


def _clear_model_cache() -> None:
    with _MODEL_LOCK:
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
    """현재(current) 모델을 캐시하되, 파일 변경(mtime) 시 자동으로 재로딩."""
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
        _clear_model_cache()
        return None

    run_id = info.get("run_id")

    with _MODEL_LOCK:
        if (
            _MODEL_CACHE.model is not None
            and _MODEL_CACHE.path == str(p)
            and _MODEL_CACHE.run_id == run_id
            and _MODEL_CACHE.mtime_ns == mtime_ns
        ):
            return _MODEL_CACHE.model

    # 로딩은 락 밖에서(요청 동시성에서 잠금 시간 최소화)
    model = joblib.load(p)

    with _MODEL_LOCK:
        _MODEL_CACHE.model = model
        _MODEL_CACHE.path = str(p)
        _MODEL_CACHE.run_id = run_id
        _MODEL_CACHE.mtime_ns = mtime_ns

    return model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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

    proba = model.predict_proba(req.features)[0][1]
    return {"p_win": float(proba)}
