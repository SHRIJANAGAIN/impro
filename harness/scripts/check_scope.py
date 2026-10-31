#!/usr/bin/env python3
"""List repository files outside the declared scope prefixes.

A change that touches a file outside its scope is a review failure even when it
is correct. Run this before reporting:

    python scripts/check_scope.py . src tests

Exit code is 1 when an out-of-scope file exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKIP = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("scope", nargs="+", help="allowed path prefixes")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    prefixes = tuple(Path(part).as_posix().strip("/") + "/" for part in args.scope)
    outside: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP.intersection(path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if not rel.startswith(prefixes):
            outside.append(rel)
    for rel in outside:
        print(rel)
    if outside:
        print(f"{len(outside)} file(s) outside the declared scope", file=sys.stderr)
        return 1
    print("scope clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
