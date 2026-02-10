from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from balanceops.datasets.bundle import DatasetBundle


@dataclass(frozen=True)
class DatasetSpec:
    """Loader에 전달되는 범용 스펙.

    - kind: loader 종류 (예: csv, sklearn)
    - name: 데이터셋 표시용 이름(선택)
    - params: loader별 파라미터(예: path, target_col, ...)
    - split: split 관련 힌트(학습 파이프라인에서 사용할 수 있음)
    """

    kind: str
    name: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    split: dict[str, Any] = field(default_factory=dict)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "params": self.params,
            "split": self.split,
            "note": self.note,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "DatasetSpec":
        return DatasetSpec(
            kind=str(d.get("kind") or ""),
            name=d.get("name"),
            params=dict(d.get("params") or {}),
            split=dict(d.get("split") or {}),
            note=d.get("note"),
        )

    @staticmethod
    def from_json(path: str | Path) -> "DatasetSpec":
        p = Path(path)
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("dataset spec JSON must be an object")
        return DatasetSpec.from_dict(obj)


DatasetLoader = Callable[[DatasetSpec], DatasetBundle]


_LOADERS: dict[str, DatasetLoader] = {}


def register_loader(kind: str, loader: DatasetLoader, *, overwrite: bool = False) -> None:
    k = kind.strip().lower()
    if not k:
        raise ValueError("kind is required")
    if (k in _LOADERS) and (not overwrite):
        raise ValueError(f"loader already registered: {k}")
    _LOADERS[k] = loader


def list_loaders() -> list[str]:
    return sorted(_LOADERS.keys())


def load_dataset(spec: DatasetSpec) -> DatasetBundle:
    k = spec.kind.strip().lower()
    if not k:
        raise ValueError("spec.kind is required")
    if k not in _LOADERS:
        known = ", ".join(list_loaders()) or "(none)"
        raise ValueError(f"unknown dataset kind: {k} (known: {known})")

    bundle = _LOADERS[k](spec)

    # loader가 meta를 이미 채웠더라도, 공통 메타는 보장
    meta = dict(bundle.meta or {})
    meta.setdefault("dataset_kind", k)
    meta.setdefault("dataset_name", spec.name or k)
    meta.setdefault("dataset_spec", spec.to_dict())

    return DatasetBundle(
        X=bundle.X,
        y=bundle.y,
        feature_names=bundle.feature_names,
        meta=meta,
    )
