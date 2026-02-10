from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class DatasetBundle:
    """범용 데이터셋 컨테이너.

    - X: (n_samples, n_features)
    - y: (n_samples,)
    - feature_names: one-hot 등 변환 이후의 최종 피처명
    - meta: 재현성을 위한 메타데이터(데이터셋 스펙/해시/스키마 등)
    """

    X: np.ndarray
    y: np.ndarray
    feature_names: list[str] | None
    meta: dict[str, Any]

    def n_samples(self) -> int:
        return int(self.X.shape[0])

    def n_features(self) -> int:
        return int(self.X.shape[1])
