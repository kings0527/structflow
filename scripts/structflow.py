#!/usr/bin/env python3
"""Run the StructFlow deterministic toolkit from an unpacked skill."""

from __future__ import annotations

import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from structflow.main import main


if __name__ == "__main__":
    main()
