"""Command line for the SKT latent-recursion inference and training stages."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

COMMANDS = ("infer", "train-inner", "train-outer")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="impro mas",
        description=(
            "SKT latent-space recursion: sequential, mixture, distillation and "
            "deliberation multi-agent inference and training."
        ),
    )
    parser.add_argument("command", choices=COMMANDS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        build_parser().print_help()
        return 0
    command, rest = args[0], args[1:]
    if command not in COMMANDS:
        build_parser().error(f"unknown command: {command!r}")

    if command == "infer":
        from .inference.run import main as command_main
    elif command == "train-inner":
        from .train.train_inner import main as command_main
    else:
        from .train.train_outer import main as command_main

    previous = sys.argv
    sys.argv = [f"impro-mas-{command}", *rest]
    try:
        result = command_main()
    finally:
        sys.argv = previous
    return 0 if result is None else int(result)


__all__ = ["COMMANDS", "build_parser", "main"]
