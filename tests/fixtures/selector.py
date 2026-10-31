"""Deterministic selector used by the end-to-end tests.

It is a real subprocess reading the evidence tree, not a mock. Selection and
experience reflection arrive as different missions; the fixture answers each in
the documented reply format.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _experience() -> int:
    print(
        "<edits>"
        "Added a check-before-reporting rule to guardrails.md."
        "</edits>"
    )
    print(
        "<experience>\n"
        "cue: when the base rollout reports a command instead of its output\n"
        "lesson: put the verification rule in guardrails.md so every run pays it\n"
        "evidence: the adopted candidate appended the rule and the rollout ran the test\n"
        "confidence: medium\n"
        "</experience>"
    )
    return 0


def _selection() -> int:
    candidates = sorted((Path.cwd() / "context" / "candidates").glob("*.md"))
    if not candidates:
        print("no candidates on disk", file=sys.stderr)
        return 2
    chosen = candidates[-1].stem
    print(f"<why>Chose {chosen} after reading every candidate; it reports the check it ran.</why>")
    print(f"```choice\n{chosen}\n```")
    return 0


def main() -> int:
    prompt = sys.stdin.read()
    if "WHAT HAPPENED" in prompt:
        return _experience()
    return _selection()


if __name__ == "__main__":
    raise SystemExit(main())
