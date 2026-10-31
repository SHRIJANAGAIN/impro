from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from impro.adapter import CodingAgentAdapter
from impro.core import tree as harness_tree
from impro.substrate import CODING_SURFACE, base_tree


def test_a_rollout_fixes_the_task_and_reports_the_check(
    adapter: CodingAgentAdapter,
) -> None:
    run = adapter.execute("example", None, "base1")
    assert adapter.delivered(run)
    files = adapter.deliverable_files(run)
    assert set(files) == {"calculator.py"}
    assert "return left + right" in files["calculator.py"]
    report = adapter.deliverable_text(run)
    assert "Ran `python test_calculator.py`: ok." in report
    trajectory = adapter.trajectory(run, obs_trunc=50_000)
    assert "[ACTION]" in trajectory
    assert "[ASSISTANT]" in trajectory
    assert "[OBSERVATION]" in trajectory


def test_a_rollout_is_idempotent_by_run_id(adapter: CodingAgentAdapter) -> None:
    first = adapter.execute("example", None, "base1")
    marker = first / ".impro" / "run.json"
    before = marker.read_text(encoding="utf-8")
    second = adapter.execute("example", None, "base1")
    assert first == second
    assert marker.read_text(encoding="utf-8") == before


def test_a_failing_agent_is_recorded_as_not_ok(tmp_path: Path, repo: Path) -> None:
    failing = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
    adapter = CodingAgentAdapter(
        tasks_root=repo / "tasks",
        runs_root=tmp_path / "runs",
        harness_root=repo / "harness",
        agent_cmd=failing,
        timeout=30,
    )
    run = adapter.execute("example", None, "base1")
    meta = json.loads((run / ".impro" / "run.json").read_text(encoding="utf-8"))
    assert meta["ok"] is False
    assert meta["error"]
    view = adapter.view("example", "base1", "base1", run)
    assert not view.ok
    assert not view.delivered


def test_a_timeout_is_recorded_not_raised(tmp_path: Path, repo: Path) -> None:
    slow = f'"{sys.executable}" -c "import time; time.sleep(2)"'
    adapter = CodingAgentAdapter(
        tasks_root=repo / "tasks",
        runs_root=tmp_path / "runs",
        harness_root=repo / "harness",
        agent_cmd=slow,
        timeout=1,
    )
    run = adapter.execute("example", None, "base1", timeout=1)
    meta = json.loads((run / ".impro" / "run.json").read_text(encoding="utf-8"))
    assert meta["ok"] is False
    assert "timeout" in meta["error"]


def test_task_ids_cannot_escape_the_task_store(adapter: CodingAgentAdapter) -> None:
    with pytest.raises(ValueError, match="escapes"):
        adapter.task_prompt("../outside")


def test_tasks_are_discovered_by_task_md(tmp_path: Path, repo: Path) -> None:
    store = tmp_path / "tasks"
    (store / "billing" / "t1").mkdir(parents=True)
    (store / "billing" / "t1" / "TASK.md").write_text("do it\n", encoding="utf-8")
    (store / "auth").mkdir()
    (store / "auth" / "not-a-task.txt").write_text("x", encoding="utf-8")
    adapter = CodingAgentAdapter(
        tasks_root=store,
        runs_root=tmp_path / "runs",
        harness_root=repo / "harness",
        agent_cmd=f'"{sys.executable}" -c "print(1)"',
    )
    assert adapter.tasks() == ["billing/t1"]
    assert adapter.domain_of("billing/t1") == "billing"
    assert adapter.domain_of("solo") == "general"


def test_validate_tree_uses_the_coding_surface(
    adapter: CodingAgentAdapter, repo: Path
) -> None:
    good = base_tree(CODING_SURFACE, repo / "harness")
    adapter.validate_tree(good)
    broken = dict(good)
    broken["scripts/nope.py"] = "def broken(:\n"
    with pytest.raises(ValueError, match="does not compile"):
        adapter.validate_tree(broken)


def test_base_harness_can_be_overridden_per_rollout(
    adapter: CodingAgentAdapter, repo: Path, tmp_path: Path
) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["memory.md"] = "A custom fact for this rollout.\n"
    custom = harness_tree.write_tree(CODING_SURFACE, tree, tmp_path / "custom")
    run = adapter.execute("example", custom, "base1")
    assert "A custom fact for this rollout." in (run / ".impro" / "harness.md").read_text(
        encoding="utf-8"
    )
    assert (run / ".impro" / "harness" / "memory.md").is_file()
