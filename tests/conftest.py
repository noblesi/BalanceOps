from __future__ import annotations

import sys
from pathlib import Path

# repo root / src 를 pytest import 경로에 강제로 추가
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

root_str = str(ROOT)
src_str = str(SRC)

if root_str not in sys.path:
    sys.path.insert(0, root_str)

if src_str not in sys.path:
    sys.path.insert(0, src_str)
