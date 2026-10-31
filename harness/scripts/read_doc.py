#!/usr/bin/env python3
"""Print a text file with line numbers, bounded in both directions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

MAX_BYTES = 2_000_000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--start", type=int, default=1, help="first line, 1-based")
    parser.add_argument("--lines", type=int, default=200, help="how many lines")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(f"no such file: {args.path}", file=sys.stderr)
        return 2
    if args.path.stat().st_size > MAX_BYTES:
        print(f"refusing a file over {MAX_BYTES} bytes: {args.path}", file=sys.stderr)
        return 2
    start = max(1, args.start)
    count = max(1, min(args.lines, 2000))
    lines = args.path.read_text(encoding="utf-8", errors="replace").splitlines()
    end = min(len(lines), start - 1 + count)
    width = len(str(end))
    for number in range(start, end + 1):
        print(f"{number:>{width}}  {lines[number - 1]}")
    if end < len(lines):
        print(f"... {len(lines) - end} more lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
