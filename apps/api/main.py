from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info, load_current_model
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


def _error_response(
        request: Request, status_code: int, err: dict[str, Any]
    ) -> JSONResponse:
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


@lru_cache(maxsize=1)
def _get_model():
    return load_current_model()


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
        _get_model.cache_clear()
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

                )
            ),
        )

    proba = model.predict_proba(req.features)[0][1]
    return {"p_win": float(proba)}
