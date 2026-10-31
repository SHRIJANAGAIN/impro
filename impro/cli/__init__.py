# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The `impro` command line.

The coding workflow (``init``, ``show``, ``tasks``, ``run``, ``domain``,
``sweep``, ``lessons``, ``apply``) lives in :mod:`impro.coding_cli`. The
benchmark reproductions retain the upstream command shapes and are reachable
under this package, either as ``impro <command>`` or as the standalone
``impro-<command>`` console scripts:

    adapt   run a benchmark sweep          (upstream run_sweep)
    judge   grade a completed sweep
    report  render the aggregate report
    check   verify a benchmark install
    demo    run the deterministic demo
    setup   install pinned benchmark tools
    bridge  serve a Responses endpoint for Codex

The impro-buddy double recursion is exposed as ``impro buddy ...`` and
``impro-buddy``; it keeps its own scientific harness, verifier, runtime and
optional SkyRL training stages.

The SKT latent-recursion method is exposed as ``impro mas ...`` and
``impro-mas``, with separate inference, inner-training and outer-training
commands.
"""

from __future__ import annotations

import importlib
import sys
from typing import Sequence

from ..coding_cli import build_parser
from ..coding_cli import main as coding_main

BENCHMARK_COMMANDS = {
    "adapt": "impro.cli.run_sweep",
    "judge": "impro.cli.judge",
    "report": "impro.cli.report",
    "check": "impro.cli.check",
    "demo": "impro.cli.demo",
    "setup": "impro.cli.setup",
    "bridge": "impro.cli.bridge",
}
BUDDY_COMMANDS = {"buddy": "impro.buddy.cli"}
MAS_COMMANDS = {"mas": "impro.mas.cli"}
COMMANDS = {**BENCHMARK_COMMANDS, **BUDDY_COMMANDS, **MAS_COMMANDS}

__all__ = [
    "BENCHMARK_COMMANDS",
    "BUDDY_COMMANDS",
    "MAS_COMMANDS",
    "COMMANDS",
    "build_parser",
    "main",
]


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch a coding command or one of the benchmark commands."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in COMMANDS:
        module = importlib.import_module(COMMANDS[args[0]])
        result = module.main(args[1:])
        return 0 if result is None else int(result)
    return int(coding_main(args))
