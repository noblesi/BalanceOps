"""Cross-platform local CI check.

This tool mirrors what GitHub Actions validates in this repo:

1) ruff format --check
2) ruff check
3) pytest
4) (optional) Tabular baseline smoke
5) E2E one-shot (or skip)

Usage:
  python -m balanceops.tools.ci_check
  python -m balanceops.tools.ci_check --port 8010
  python -m balanceops.tools.ci_check --skip-e2e
  python -m balanceops.tools.ci_check --skip-e2e --include-tabular-baseline
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists() and (p / "src").exists() and (p / "apps").exists():
            return p
    return start


def _ensure_ci_env(repo_root: Path) -> None:
    """Pin paths to .ci/ unless user already configured env vars.

    This avoids polluting local data/ and artifacts/ when running quick checks.
    """
    os.environ.setdefault("BALANCEOPS_DB", str(repo_root / ".ci" / "balanceops.db"))
    os.environ.setdefault("BALANCEOPS_ARTIFACTS", str(repo_root / ".ci" / "artifacts"))
    os.environ.setdefault(
        "BALANCEOPS_CURRENT_MODEL",
        str(repo_root / ".ci" / "artifacts" / "models" / "current.joblib"),
    )
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    (repo_root / ".ci").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ci" / "artifacts" / "models").mkdir(parents=True, exist_ok=True)


def _run_tabular_baseline_smoke(repo_root: Path) -> int:
    spec = repo_root / "examples" / "dataset_specs" / "finance_credit_demo.json"
    if not spec.exists():
        print(f"[ci_check] ERROR: dataset spec not found: {spec}", file=sys.stderr)
        return 2
    return _run(
        [
            sys.executable,
            "-m",
            "balanceops.pipeline.train_tabular_baseline",
            "--dataset-spec",
            str(spec),
            "--no-auto-promote",
        ],
        cwd=repo_root,
    )


def _resolve_ruff(repo_root: Path) -> str | None:
    """Find ruff executable with sensible fallbacks (.venv first, then PATH)."""
    candidates = [
        repo_root / ".venv" / "Scripts" / "ruff.exe",  # Windows venv
        repo_root / ".venv" / "bin" / "ruff",  # Linux/macOS venv
    ]
    for p in candidates:
        if p.exists():
            return str(p)

    which = shutil.which("ruff")
    if which:
        return which

    return None


def _run(cmd: list[str], *, cwd: Path) -> int:
    print(f"[ci_check] $ {' '.join(cmd)}")
    p = subprocess.run(cmd, cwd=str(cwd))
    return int(p.returncode)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="BalanceOps local CI check (cross-platform).")
    ap.add_argument("--port", type=int, default=8010, help="port for E2E server (default 8010)")
    ap.add_argument("--skip-e2e", action="store_true", help="skip E2E step")
    ap.add_argument(
        "--include-tabular-baseline",
        action="store_true",
        help="run tabular baseline smoke (finance_credit_demo.json, no-auto-promote)",
    )
    ap.add_argument(
        "--no-ci-env",
        action="store_true",
        help="do not force .ci/ sandbox env vars (use existing env/default settings)",
    )
    return ap


def build_step_names(*, skip_e2e: bool, include_tabular_baseline: bool) -> list[str]:
    """Return the ordered list of step names for the given option set.

    Pure function: safe to regression-test without executing subprocesses.
    """
    names = ["ruff format --check", "ruff check", "pytest"]
    if include_tabular_baseline:
        names.append("tabular baseline smoke (no-auto-promote)")
    names.append("skip e2e" if skip_e2e else "e2e")
    return names


def run_ci_check(
    *, port: int, skip_e2e: bool, include_tabular_baseline: bool, no_ci_env: bool
) -> int:
    repo_root = _find_repo_root(Path.cwd())
    print(f"[ci_check] repo_root: {repo_root}")

    if not no_ci_env:
        _ensure_ci_env(repo_root)

    ruff = _resolve_ruff(repo_root)
    if not ruff:
        print(
            "[ci_check] ERROR: ruff not found. Run: python -m pip install -e '.[dev]'",
            file=sys.stderr,
        )
        return 2

    plan = build_step_names(skip_e2e=skip_e2e, include_tabular_baseline=include_tabular_baseline)

    runnables: dict[str, Callable[[], int]] = {
        "ruff format --check": lambda: _run([ruff, "format", "--check", "."], cwd=repo_root),
        "ruff check": lambda: _run([ruff, "check", "."], cwd=repo_root),
        "pytest": lambda: _run([sys.executable, "-m", "pytest", "-q"], cwd=repo_root),
        "tabular baseline smoke (no-auto-promote)": lambda: _run_tabular_baseline_smoke(repo_root),
        "skip e2e": lambda: 0,
        "e2e": lambda: _run(
            [sys.executable, "-m", "balanceops.tools.e2e", "--port", str(port)],
            cwd=repo_root,
        ),
    }

    missing = [name for name in plan if name not in runnables]
    if missing:
        print(f"[ci_check] ERROR: unknown step name(s) in plan: {missing}", file=sys.stderr)
        return 2

    steps: list[tuple[str, Callable[[], int]]] = [(name, runnables[name]) for name in plan]

    total = len(steps)
    for i, (name, fn) in enumerate(steps, start=1):
        print(f"[ci_check] step {i}/{total}: {name}")
        code = fn()
        if code != 0:
            return code

    print("[ci_check] OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return run_ci_check(
        port=int(args.port),
        skip_e2e=bool(args.skip_e2e),
        include_tabular_baseline=bool(args.include_tabular_baseline),
        no_ci_env=bool(args.no_ci_env),
    )


if __name__ == "__main__":
    raise SystemExit(main())
