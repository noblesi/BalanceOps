from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DummyBalanceModel:
    seed: int
    w: np.ndarray
    b: float

    def predict_proba(self, x):
        x = np.asarray(x, dtype=float)
        if x.ndim == 1:
            x = x.reshape(1, -1)

        n_in = x.shape[1]
        w = self.w
        if n_in < w.size:
            w = w[:n_in]
        elif n_in > w.size:
            w = np.pad(w, (0, n_in - w.size))

        z = x @ w + self.b
        p = 1.0 / (1.0 + np.exp(-z))
        p = np.clip(p, 1e-6, 1.0 - 1e-6)
        return np.stack([1.0 - p, p], axis=1)
