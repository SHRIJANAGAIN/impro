from __future__ import annotations

from pathlib import Path

import pytest

from impro.core.library import Library, domain_dir, has_experience, slug
from impro.substrate import CODING_SURFACE, base_tree


def _library(tmp_path: Path, domain: str = "billing") -> Library:
    return Library(root=tmp_path / "library", domain=domain, surface=CODING_SURFACE)


def _experience() -> dict:
    return {
        "cue": "a ledger whose totals disagree with its rows",
        "lesson": "recompute from rows before trusting the total",
        "evidence": "the adopted rollout recomputed and matched",
        "confidence": "medium",
    }


def test_names_are_path_safe_and_deterministic() -> None:
    assert slug("area/task") == "area__task"
    assert domain_dir("a/b") == "a__b"
    assert domain_dir("billing") == "billing"
    assert domain_dir(" / ") == "__"


def test_experience_requires_all_three_prose_fields() -> None:
    assert has_experience(_experience())
    assert not has_experience({"cue": "x", "lesson": "y"})
    assert not has_experience(None)


def test_add_without_experience_writes_nothing(tmp_path: Path, repo: Path) -> None:
    library = _library(tmp_path)
    tree = base_tree(CODING_SURFACE, repo / "harness")
    assert library.add("billing-1", tree, why="no lesson") is None
    assert not library.exists()
    assert library.entries() == []


def test_add_stores_the_full_tree_index_and_experience(tmp_path: Path, repo: Path) -> None:
    library = _library(tmp_path)
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["memory.md"] = "Use the ledger table as the source of truth.\n"
    entry = library.add(
        "billing-1",
        tree,
        why="the adopted harness recomputed totals",
        label="agg2",
        run_id="run-2",
        experience=_experience(),
    )
    assert entry is not None
    assert library.exists()
    assert library.entries() == ["billing-1"]
    assert library.tree_of("billing-1") == tree
    index = library.index.read_text(encoding="utf-8")
    assert "billing-1" in index
    assert "a ledger whose totals disagree" in index
    experience = (entry / "EXPERIENCE.md").read_text(encoding="utf-8")
    assert "agg2" in experience
    assert "Transferable lesson" in experience


def test_forget_and_retain_keep_the_prefix(tmp_path: Path, repo: Path) -> None:
    library = _library(tmp_path)
    tree = base_tree(CODING_SURFACE, repo / "harness")
    for name in ("t1", "t2", "t3"):
        library.add(name, tree, experience=_experience())
    assert library.entries() == ["t1", "t2", "t3"]

    library.retain(["t1", "t2"])
    assert library.entries() == ["t1", "t2"]
    library.forget(["t1"])
    assert library.entries() == ["t2"]
    assert "t1" not in library.index.read_text(encoding="utf-8")
    library.retain([])
    assert library.entries() == []
    assert library.context_dir() is None


def test_grader_verdicts_are_refused(tmp_path: Path, repo: Path) -> None:
    library = _library(tmp_path)
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["memory.md"] = 'reference "pass_rate": 1\n'
    with pytest.raises(ValueError):
        library.add("t1", tree, experience=_experience())


def test_each_domain_gets_its_own_directory(tmp_path: Path, repo: Path) -> None:
    tree = base_tree(CODING_SURFACE, repo / "harness")
    one = _library(tmp_path, "billing")
    two = _library(tmp_path, "auth")
    one.add("t1", tree, experience=_experience())
    two.add("t2", tree, experience=_experience())
    assert one.entries() == ["t1"]
    assert two.entries() == ["t2"]
    assert one.dir != two.dir
