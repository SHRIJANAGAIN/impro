from __future__ import annotations

import json
import shutil
from pathlib import Path

from impro.adapter import CodingAgentAdapter
from impro.core import schedule
from impro.core.library import Library
from impro.core.proposer import Proposer


def _adapter(tmp_path: Path, store: Path, agent_cmd: str, selector_cmd: str) -> CodingAgentAdapter:
    return CodingAgentAdapter(
        tasks_root=store,
        runs_root=tmp_path / "runs",
        harness_root=Path(__file__).resolve().parents[1] / "harness",
        agent_cmd=agent_cmd,
        selector_cmd=selector_cmd,
        timeout=120,
    )


def _proposer(adapter: CodingAgentAdapter, tmp_path: Path) -> Proposer:
    return Proposer(
        spec=adapter.spec.channels["proposer"],
        audit_dir=tmp_path / "runs" / "_audit",
        attempts=1,
    )


def _selector(adapter: CodingAgentAdapter, tmp_path: Path) -> Proposer:
    return Proposer(
        spec=adapter.spec.channels["selector"],
        audit_dir=tmp_path / "runs" / "_audit",
        attempts=1,
    )


def _libs(adapter: CodingAgentAdapter, tmp_path: Path, domain: str, modes):
    surface = adapter.substrate.surface()
    return {
        mode: Library(root=tmp_path / "library" / mode, domain=domain, surface=surface)
        for mode in modes
    }


def test_one_task_both_modes_end_to_end(
    tmp_path: Path, repo: Path, agent_cmd: str, selector_cmd: str
) -> None:
    adapter = _adapter(tmp_path, repo / "tasks", agent_cmd, selector_cmd)
    prop = _proposer(adapter, tmp_path)
    modes = ("agg", "seq")
    result = schedule.run_task(
        "example",
        1,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        modes=modes,
        libraries=_libs(adapter, tmp_path, "general", modes),
    )
    assert result.status == "ok"
    assert not result.errors
    for mode in modes:
        ledger = result.modes[mode]["ledger"]
        assert (ledger["R"], ledger["P"]) == (4, 3)
        chosen = result.selections[mode]
        assert chosen["ok"]
        assert chosen["chosen_label"] in ({"agg1"} if mode == "agg" else {"c1"})
        run_dir = Path(chosen["chosen_run_dir"])
        assert "return left + right" in (run_dir / "calculator.py").read_text(encoding="utf-8")
        harness = (
            tmp_path
            / "runs"
            / f"impro-workspace-{mode}1"
            / "example"
            / "harnesses"
            / chosen["chosen_label"]
            / "guardrails.md"
        )
        assert "run it before claiming the change works" in harness.read_text(encoding="utf-8")

    calls = len(prop._calls)
    resumed = schedule.run_task(
        "example",
        1,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        modes=modes,
        libraries=_libs(adapter, tmp_path, "general", modes),
    )
    assert resumed.status == "skipped"
    assert len(prop._calls) == calls


def test_a_domain_threads_the_library_forward(
    tmp_path: Path, repo: Path, agent_cmd: str, selector_cmd: str
) -> None:
    store = tmp_path / "tasks"
    for name in ("t1", "t2"):
        shutil.copytree(repo / "tasks" / "example", store / "area" / name)
    adapter = _adapter(tmp_path, store, agent_cmd, selector_cmd)
    prop = _proposer(adapter, tmp_path)
    selector = _selector(adapter, tmp_path)
    modes = ("agg",)
    out = schedule.run_domain(
        "area",
        ["area/t1", "area/t2"],
        2,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        library_root=tmp_path / "library",
        modes=modes,
        selector_prop=selector,
    )
    assert (out["done"], out["failed"]) == (2, 0)
    for mode in modes:
        library = Library(
            root=tmp_path / "library" / mode,
            domain="area",
            surface=adapter.substrate.surface(),
        )
        assert library.entries() == ["area__t1", "area__t2"]
        assert library.context_dir() is not None

    summary = json.loads(
        (
            tmp_path / "runs" / "impro-workspace-agg2" / "area__t2" / "summary.json"
        ).read_text(encoding="utf-8")
    )
    for mode in modes:
        assert summary["modes"][mode]["ledger"]["R"] == 8
        assert summary["modes"][mode]["ledger"]["P"] == 6
        sel = summary["selections"][mode]
        assert sel["ok"]
        assert sel["experience"]["lesson"]

    second_context = (
        tmp_path
        / "runs"
        / "impro-workspace-agg2"
        / "area__t2"
        / "context"
        / "inv1"
        / "library"
        / "harnesses"
    )
    assert (second_context / "area__t1").is_dir()

    calls = (len(prop._calls), len(selector._calls))
    resumed = schedule.run_domain(
        "area",
        ["area/t1", "area/t2"],
        2,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        library_root=tmp_path / "library",
        modes=modes,
        selector_prop=selector,
    )
    assert (resumed["done"], resumed["failed"]) == (2, 0)
    assert (len(prop._calls), len(selector._calls)) == calls


def test_a_failed_base_marks_the_task_without_running_stages(
    tmp_path: Path, repo: Path, selector_cmd: str
) -> None:
    adapter = _adapter(
        tmp_path,
        repo / "tasks",
        '"definitely-not-a-real-command-xyz"',
        selector_cmd,
    )
    prop = _proposer(adapter, tmp_path)
    result = schedule.run_task(
        "example",
        1,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        modes=("agg",),
    )
    assert result.status == "base-failed"
    assert result.errors == ["no base rollout produced anything"]
    assert prop._calls == []


def test_the_budget_identity_is_asserted_for_every_mode(
    tmp_path: Path, repo: Path, agent_cmd: str, selector_cmd: str
) -> None:
    adapter = _adapter(tmp_path, repo / "tasks", agent_cmd, selector_cmd)
    prop = _proposer(adapter, tmp_path)
    result = schedule.run_task(
        "example",
        2,
        adapter=adapter,
        prop=prop,
        runs_root=tmp_path / "runs",
        modes=("agg",),
        libraries=_libs(adapter, tmp_path, "general", ("agg",)),
        selector_prop=_selector(adapter, tmp_path),
    )
    assert result.status == "ok"
    ledger = result.modes["agg"]["ledger"]
    assert (ledger["R"], ledger["P"]) == (8, 6)
    assert ledger["session_attempts"] == ledger["expected_P"]
