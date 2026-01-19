from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class GitInfo:
    commit: str | None
    branch: str | None
    dirty: bool


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def get_git_info() -> GitInfo:
    try:
        commit = _run(["git", "rev-parse", "HEAD"])
        branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
        dirty = bool(_run(["git", "status", "--porcelain"]))
        return GitInfo(commit=commit, branch=branch, dirty=dirty)
    except Exception:
        return GitInfo(commit=None, branch=None, dirty=False)
