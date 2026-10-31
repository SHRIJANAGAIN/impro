"""A deterministic agent used by the test suite.

It is not a model. It is a real subprocess that reads the workspace and makes a
real edit, so the tests exercise the framework's filesystem, prompt, harvest and
trajectory paths without a network or an API key.

Two roles, chosen by what is on disk:

- rollout: ``calculator.py`` exists -> fix ``add`` and run the test.
- improver: ``context/harness/`` exists -> append one rule to ``guardrails.md``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _improve(root: Path) -> int:
    harness = root / "context" / "harness"
    guardrails = harness / "guardrails.md"
    if not guardrails.is_file():
        print(f"no guardrails at {guardrails}", file=sys.stderr)
        return 2
    rule = "- When a test exists, run it before claiming the change works."
    body = guardrails.read_text(encoding="utf-8")
    if rule not in body:
        guardrails.write_text(body.rstrip() + "\n" + rule + "\n", encoding="utf-8")
    print(
        "<notes>Added one rule to guardrails.md because the base rollout reported a "
        "check it had not run.</notes>"
    )
    return 0


def _rollout(root: Path) -> int:
    calculator = root / "calculator.py"
    if not calculator.is_file():
        print("no calculator.py in the workspace", file=sys.stderr)
        return 2
    body = calculator.read_text(encoding="utf-8")
    fixed = body.replace("return left - right", "return left + right")
    if fixed == body:
        print("add() was already fixed")
    else:
        calculator.write_text(fixed, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "test_calculator.py"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip() or proc.stdout.strip(), file=sys.stderr)
        return proc.returncode
    print("Changed calculator.py: add() now returns left + right.")
    print("Ran `python test_calculator.py`: ok.")
    return 0


def main() -> int:
    root = Path.cwd()
    if (root / "context" / "harness").is_dir():
        return _improve(root)
    return _rollout(root)


if __name__ == "__main__":
    raise SystemExit(main())
