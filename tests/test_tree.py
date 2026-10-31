from __future__ import annotations

from pathlib import Path

import pytest

from impro.core import tree as harness_tree
from impro.substrate import CODING_SURFACE, base_tree, render

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_harness_is_valid_and_has_every_component(repo: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    census = harness_tree.validate(
        CODING_SURFACE, tree, allow_subagents=True
    )
    assert census["always_on_chars"] > 0
    assert census["skills"] >= 1
    assert census["sub_agents"] >= 1
    assert census["scripts"] >= 3
    assert "systemprompt.md" in tree
    assert "skills/verify-change/SKILL.md" in tree
    assert "scripts/check_scope.py" in tree


def test_render_inlines_always_on_and_indexes_the_rest(repo: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    text = render(CODING_SURFACE, tree)
    assert "## systemprompt.md" in text
    assert "## guardrails.md" in text
    assert "skills/verify-change/SKILL.md" in text
    assert "sub_agents/reviewer/AGENT.md" in text
    assert "scripts/check_scope.py" in text
    assert "description:" not in text


def test_write_read_roundtrip(repo: Path, tmp_path: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    dest = harness_tree.write_tree(CODING_SURFACE, tree, tmp_path / "out")
    assert harness_tree.read_tree(CODING_SURFACE, dest) == tree
    assert harness_tree.is_tree(CODING_SURFACE, dest)


def test_off_surface_files_are_reported_not_read(repo: Path, tmp_path: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    dest = harness_tree.write_tree(CODING_SURFACE, tree, tmp_path / "out")
    (dest / "notes.txt").write_text("not part of the harness", encoding="utf-8")
    rejected: list[str] = []
    got = harness_tree.read_tree(CODING_SURFACE, dest, rejected=rejected)
    assert "notes.txt" not in got
    assert rejected == ["notes.txt"]


def test_untriggered_skill_is_rejected(repo: Path) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["skills/orphan/SKILL.md"] = "---\ndescription: a skill nobody calls\n---\n\nDo it.\n"
    with pytest.raises(ValueError, match="orphan.*never named"):
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)


def test_skill_without_description_is_rejected(repo: Path) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["skills/verify-change/SKILL.md"] = "---\nname: verify-change\n---\n\nNo description.\n"
    with pytest.raises(ValueError, match="description"):
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)


def test_broken_script_is_rejected(repo: Path) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["scripts/broken.py"] = "def f(:\n    pass\n"
    with pytest.raises(ValueError, match="does not compile"):
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)


def test_a_skill_may_not_invoke_a_missing_script(repo: Path) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["skills/verify-change/SKILL.md"] = (
        "---\ndescription: verify\n---\n\nRun `python scripts/not_shipped.py`.\n"
    )
    with pytest.raises(ValueError, match="not_shipped.py.*not in the harness"):
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)


def test_always_on_cap_is_enforced(repo: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    with pytest.raises(ValueError, match="over the 100 cap"):
        harness_tree.validate(CODING_SURFACE, tree, always_on_max=100)


def test_path_traversal_is_off_the_surface() -> None:
    assert not harness_tree.is_allowed(CODING_SURFACE, "../secret.md")
    assert not harness_tree.is_allowed(CODING_SURFACE, "scripts/../../secret.py")
    assert not harness_tree.is_allowed(CODING_SURFACE, "/etc/passwd")


def test_python_plugins_are_on_the_surface() -> None:
    assert harness_tree.is_allowed(CODING_SURFACE, "plugins/check_scope.py")
    assert harness_tree.is_allowed(CODING_SURFACE, "plugins/hooks.ts")


def test_validate_reports_every_problem_at_once(repo: Path) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["skills/orphan/SKILL.md"] = "---\ndescription: nobody calls me\n---\n\nDo it.\n"
    tree["scripts/broken.py"] = "def f(:\n"
    with pytest.raises(ValueError) as caught:
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)
    message = str(caught.value)
    assert "|" in message
    assert "does not compile" in message
    assert "orphan" in message
