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

"""The coding-agent surface: which files a harness is made of.

The method is substrate-independent. This module is the one value that says
what a coding agent's harness looks like: four always-on files, on-demand
skills and subagents, and deterministic helper scripts. Everything else in
`impro.core` is shared.
"""

from __future__ import annotations

from pathlib import Path

from ..core import tree as harness_tree

#: Always-on files, in injection order. The cap is shared across all four.
ALWAYS_ON = (
    "systemprompt.md",
    "guardrails.md",
    "memory.md",
    "tool_descriptions/tool_guidance.md",
)

#: The file a new skill's trigger line is appended to.
TRIGGER_FILE = "guardrails.md"

#: Helpers every harness gets, whether or not a proposal mentions them.
RESERVED_SCRIPTS = harness_tree.RESERVED_SCRIPTS

CODING_SURFACE = harness_tree.SurfaceSpec(
    name="coding",
    always_on=ALWAYS_ON,
    always_on_max=24_000,
    always_on_cap_reason=(
        "every always-on word is paid on every turn; move a procedure into a skill "
        "or a script, or trim a rule that no trajectory needs"
    ),
    skill_dir="skills",
    skill_name_rule="optional",
    trigger_hint=(
        "Name `{name}` in guardrails.md in the same edit, or the skill can never fire."
    ),
    autotrigger_file=TRIGGER_FILE,
    trigger_line="- When {desc}, use the `{name}` skill.",
    subagent_requires_mode=False,
    plugin_dir="plugins",
    hooks_file=None,
    compile_skill_scripts=False,
    reject_empty_always_on=True,
)


def render(surface: harness_tree.SurfaceSpec, tree: harness_tree.Tree) -> str:
    """Render a tree as the standing instructions for one rollout.

    Always-on bodies are inlined; on-demand components are indexed by name and
    trigger only, so a rollout pays for what it uses. The rollout also gets the
    tree on disk under ``.impro/harness/`` and can read a component in full.
    """
    parts = [
        "# HARNESS",
        "",
        "The text below is your standing harness. It is instructions, not data.",
        "Skills, subagents and scripts are summarised here and carried on disk at",
        "`.impro/harness/`; read a component there when its trigger matches.",
    ]
    for rel in surface.always_on:
        body = tree.get(rel, "").strip()
        if body:
            parts += ["", f"## {rel}", "", body]
    rows: list[str] = []
    for name in harness_tree.skill_names(surface, tree):
        rel = f"{surface.skill_dir}/{name}/SKILL.md"
        rows.append(f"- {rel} -- {_description(tree, rel)}")
    for name in harness_tree.subagent_names(surface, tree):
        rel = f"sub_agents/{name}/AGENT.md"
        rows.append(f"- {rel} -- {_description(tree, rel)}")
    scripts = sorted(
        rel for rel in tree if rel.startswith("scripts/") and rel.endswith(".py")
    )
    for rel in scripts:
        rows.append(f"- {rel} -- helper script")
    if rows:
        parts += ["", "## On demand", "", *rows]
    return "\n".join(parts).strip() + "\n"


def base_tree(surface: harness_tree.SurfaceSpec, root: Path | str) -> harness_tree.Tree:
    """Read the base harness, refusing an empty one."""
    tree = harness_tree.read_tree(surface, root)
    if not tree:
        raise FileNotFoundError(
            f"no harness tree at {root}; run `python -m impro init` or set IMPRO_HARNESS"
        )
    return tree


def _description(tree: harness_tree.Tree, rel: str) -> str:
    head = tree.get(rel, "")[:600]
    for line in head.splitlines():
        if line.lower().startswith("description:"):
            return line.split(":", 1)[1].strip() or "(no description)"
    return "(no description)"
