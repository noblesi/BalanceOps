from __future__ import annotations

import platform
import sys
from importlib import metadata

from balanceops.common.gitinfo import get_git_info


def _safe_pkg_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def get_build_info() -> dict[str, object]:
    """빌드/실행 식별 정보.

    - 배포/서빙 환경에서 "지금 보고 있는 서버가 어떤 커밋인가"를 확인하기 위한 용도.
    - 로컬에서는 대시보드 헤더에서 함께 보여줄 수 있다.
    """
    git = get_git_info()
    pkg_version = _safe_pkg_version("balanceops")

    return {
        "package": {"name": "balanceops", "version": pkg_version},
        "git": {"commit": git.commit, "branch": git.branch, "dirty": git.dirty},
        "python": {"version": sys.version.split()[0]},
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }
