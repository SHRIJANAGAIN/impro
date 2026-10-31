#!/usr/bin/env python3
"""Unpack a zip into a directory, refusing entries that escape it."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)

    if not args.archive.is_file():
        print(f"no such archive: {args.archive}", file=sys.stderr)
        return 2
    args.destination.mkdir(parents=True, exist_ok=True)
    root = args.destination.resolve()
    written = 0
    with zipfile.ZipFile(args.archive) as bundle:
        for info in bundle.infolist():
            target = (root / info.filename).resolve()
            if root not in target.parents and target != root:
                print(f"refusing to escape the destination: {info.filename}", file=sys.stderr)
                return 2
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read(info))
            written += 1
    print(f"unpacked {written} files into {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
