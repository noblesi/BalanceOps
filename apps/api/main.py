from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from balanceops.common.config import get_settings
from balanceops.registry.current import get_current_model_info, load_current_model
from balanceops.tracking.init_db import init_db


app = FastAPI(title="BalanceOps API")


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


@lru_cache(maxsize=1)
def _get_model():
    return load_current_model()


@app.on_event("startup")
def _startup():
    s = get_settings()
    init_db(s.db_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/model")
def model_info() -> dict[str, Any]:
    return get_current_model_info()


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
                hint="Run scripts/train_dummy.ps1 (or: python -m balanceops.pipeline.train_dummy) to promote one.",
            ),
        )

    proba = model.predict_proba(req.features)[0][1]
    return {"p_win": float(proba)}
