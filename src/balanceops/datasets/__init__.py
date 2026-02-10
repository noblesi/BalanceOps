from __future__ import annotations

# built-in loaders registration
from balanceops.datasets import csv_loader as _csv_loader  # noqa: F401
from balanceops.datasets.bundle import DatasetBundle
from balanceops.datasets.registry import (
    DatasetLoader,
    DatasetSpec,
    list_loaders,
    load_dataset,
    register_loader,
)

__all__ = [
    "DatasetBundle",
    "DatasetLoader",
    "DatasetSpec",
    "list_loaders",
    "load_dataset",
    "register_loader",
]
