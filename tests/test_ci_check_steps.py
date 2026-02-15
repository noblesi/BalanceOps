from __future__ import annotations

from balanceops.tools.ci_check import build_step_names


def test_ci_check_step_names_default() -> None:
    assert build_step_names(skip_e2e=False, include_tabular_baseline=False) == [
        "ruff format --check",
        "ruff check",
        "pytest",
        "e2e",
    ]


def test_ci_check_step_names_skip_e2e() -> None:
    assert build_step_names(skip_e2e=True, include_tabular_baseline=False) == [
        "ruff format --check",
        "ruff check",
        "pytest",
        "skip e2e",
    ]


def test_ci_check_step_names_include_tabular_baseline() -> None:
    assert build_step_names(skip_e2e=True, include_tabular_baseline=True) == [
        "ruff format --check",
        "ruff check",
        "pytest",
        "tabular baseline smoke (no-auto-promote)",
        "skip e2e",
    ]
