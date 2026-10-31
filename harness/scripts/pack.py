#!/usr/bin/env python3
"""Pack a directory into a zip, excluding VCS and cache directories."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

SKIP = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print(f"not a directory: {args.source}", file=sys.stderr)
        return 2
    written = 0
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(args.source.rglob("*")):
            if not path.is_file() or SKIP.intersection(path.parts):
                continue
            bundle.write(path, path.relative_to(args.source).as_posix())
            written += 1
    print(f"packed {written} files into {args.archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
