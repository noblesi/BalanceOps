from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    db_path: str
    artifacts_dir: str
    current_model_path: str


def get_settings() -> Settings:
    # 로컬 개발에서는 .env가 있으면 읽고, 배포에서는 환경변수만으로 동작
    if load_dotenv is not None:
        load_dotenv(override=False)

    db_path = os.getenv("BALANCEOPS_DB", "data/balanceops.db")
    artifacts_dir = os.getenv("BALANCEOPS_ARTIFACTS", "artifacts")
    current_model_path = os.getenv("BALANCEOPS_CURRENT_MODEL", "artifacts/models/current.joblib")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
    Path(current_model_path).parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        db_path=db_path,
        artifacts_dir=artifacts_dir,
        current_model_path=current_model_path,
    )
