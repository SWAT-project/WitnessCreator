#!/usr/bin/env python3
"""Builds the single-file ``witnesscreator.pyz`` (a zipapp, stdlib only).

usage: tools/build_pyz.py [OUTPUT]   (default: dist/witnesscreator.pyz)
"""

import shutil
import sys
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "witnesscreator"


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "witnesscreator.pyz"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "app"
        shutil.copytree(PACKAGE, staging / "witnesscreator", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        zipapp.create_archive(
            staging,
            target=target,
            interpreter="/usr/bin/env python3",
            main="witnesscreator.cli:main",
            compressed=True,
        )
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
