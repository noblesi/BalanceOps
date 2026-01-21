from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from balanceops.registry.current import get_current_model_info, load_current_model
from balanceops.tracking.init_db import init_db
from balanceops.common.config import get_settings


app = FastAPI(title="BalanceOps API")


class PredictRequest(BaseModel):
    features: list[float]


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
        # 캐시된 깨진 상태를 날리고, 사용자에게 명확히 안내
        _get_model.cache_clear()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load current model. Re-promote a valid model. ({type(e).__name__}: {e})",
        )

    if model is None:
        raise HTTPException(status_code=404, detail="No current model promoted yet.")

    proba = model.predict_proba(req.features)[0][1]
    return {"p_win": float(proba)}
