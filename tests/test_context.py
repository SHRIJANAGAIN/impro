from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from impro.adapter import CodingAgentAdapter
from impro.core import context
from impro.core.spec import RunView


def _view(run_dir: Path, label: str) -> RunView:
    return RunView(
        label=label,
        run_id=f"id-{label}",
        run_dir=run_dir,
        ok=True,
        delivered=True,
    )


def test_build_writes_task_rollouts_harness_and_source(
    adapter: CodingAgentAdapter, repo: Path, tmp_path: Path
) -> None:
    base1 = adapter.execute("example", None, "base1")
    base2 = adapter.execute("example", None, "base2")
    dest = tmp_path / "context-inv1"
    built = context.build(
        dest,
        adapter,
        "example",
        [_view(base1, "base1"), _view(base2, "base2")],
        harness_dir=repo / "harness",
    )
    assert built.rollouts == ["base1", "base2"]
    assert built.harness_files > 5
    assert built.source_files == 2
    assert (dest / "task.md").read_text(encoding="utf-8").startswith("# Fix the calculator")
    assert (dest / "rollouts" / "base1.md").is_file()
    assert (dest / "rollouts" / "base2.md").is_file()
    assert (dest / "harness" / "systemprompt.md").is_file()
    assert (dest / "source" / "calculator.py").is_file()
    assert (dest / "deliverables" / "base1" / "INDEX.md").is_file()
    mission = context.mission(built, job="Improve the harness.")
    assert "Improve the harness." in mission
    assert "context/rollouts/" in mission
    assert "context/harness/" in mission


def test_answer_keys_never_enter_the_evidence_tree(
    adapter: CodingAgentAdapter, repo: Path, tmp_path: Path
) -> None:
    source = repo / "tasks" / "example" / "source"
    (source / "reference_answer.txt").write_text('"pass_rate": 1\n', encoding="utf-8")
    adapter = replace(adapter, leak_globs=("reference_answer.txt",))
    try:
        run = adapter.execute("example", None, "base1")
        dest = tmp_path / "context-inv1"
        context.build(
            dest,
            adapter,
            "example",
            [_view(run, "base1")],
            harness_dir=repo / "harness",
        )
        assert not list(dest.rglob("reference_answer.txt"))
        assert list((dest / "source").iterdir())
        with pytest.raises(ValueError, match="grader verdict"):
            context.assert_no_grader_verdicts(repo / "tasks" / "example" / "source")
    finally:
        (source / "reference_answer.txt").unlink(missing_ok=True)


def test_grader_markers_are_refused_in_harness_text(tmp_path: Path) -> None:
    tree = {"memory.md": 'the answer had a "pass_rate": 1\n'}
    with pytest.raises(ValueError, match="pass_rate"):
        context.assert_tree_has_no_grader_verdicts(tree)
    with pytest.raises(ValueError, match="deterministic_eval_summary"):
        context.assert_tree_has_no_grader_verdicts({"deterministic_eval_summary.md": "x"})


def test_build_is_an_exact_rebuild(
    adapter: CodingAgentAdapter, repo: Path, tmp_path: Path
) -> None:
    run = adapter.execute("example", None, "base1")
    dest = tmp_path / "context-inv1"
    context.build(dest, adapter, "example", [_view(run, "base1")])
    (dest / "stale.txt").write_text("old", encoding="utf-8")
    context.build(dest, adapter, "example", [_view(run, "base1")])
    assert not (dest / "stale.txt").exists()
    assert (dest / "task.md").is_file()
