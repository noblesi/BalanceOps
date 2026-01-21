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
def predict(req: PredictRequest) -> dict[str, Any]:
    model = _get_model()
    if model is None:
        _get_model.cache_clear()
        model = _get_model()
    if model is None:
        raise HTTPException(status_code=404, detail="No current model promoted yet.")
    x = np.array(req.features, dtype=float).reshape(1, -1)
    if hasattr(model, "predict_proba"):
        p = float(model.predict_proba(x)[0, 1])
        return {"p_win": p}
    y = model.predict(x)
    return {"pred": int(y[0])}
