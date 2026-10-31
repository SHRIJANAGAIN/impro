from __future__ import annotations

from pathlib import Path

from impro.adapter import CodingAgentAdapter
from impro.core import selection
from impro.core.proposer import Proposer
from impro.core.spec import ChannelSpec, RunView


def _view(run_dir: Path, label: str) -> RunView:
    return RunView(
        label=label,
        run_id=f"id-{label}",
        run_dir=run_dir,
        ok=True,
        delivered=True,
    )


def _selector(cmd: str, tmp_path: Path) -> Proposer:
    return Proposer(
        spec=ChannelSpec("command", "agent", command=cmd, timeout=60),
        audit_dir=tmp_path / "audit",
        attempts=1,
    )


def test_trivial_selection_takes_the_single_final(
    adapter: CodingAgentAdapter, tmp_path: Path
) -> None:
    run = adapter.execute("example", None, "agg1")
    sel = selection.trivial_selection(
        "example",
        1,
        "agg",
        {"agg1": _view(run, "agg1")},
        adapter=adapter,
        work_dir=tmp_path / "work",
    )
    assert sel.ok
    assert sel.trivial
    assert sel.chosen_label == "agg1"
    assert sel.chosen_id == "A"
    assert "selector session" in sel.why
    persisted = tmp_path / "work" / "selection" / "agg1" / "selection.json"
    assert persisted.is_file()


def test_trivial_selection_drops_a_non_delivered_candidate(
    adapter: CodingAgentAdapter, tmp_path: Path
) -> None:
    missing = tmp_path / "missing"
    sel = selection.trivial_selection(
        "example",
        1,
        "agg",
        {
            "agg1": RunView(
                label="agg1",
                run_id="x",
                run_dir=missing,
                ok=True,
                delivered=False,
            )
        },
        adapter=adapter,
        work_dir=tmp_path / "work",
    )
    assert not sel.ok
    assert sel.dropped == ["agg1"]
    assert "no candidate" in sel.error


def test_a_real_selector_session_picks_from_an_anonymised_pool(
    adapter: CodingAgentAdapter, selector_cmd: str, tmp_path: Path
) -> None:
    one = adapter.execute("example", None, "agg1")
    two = adapter.execute("example", None, "agg2")
    candidates = {"agg1": _view(one, "agg1"), "agg2": _view(two, "agg2")}
    sel = selection.run_selection(
        "example",
        2,
        "agg",
        candidates,
        adapter=adapter,
        prop=_selector(selector_cmd, tmp_path),
        work_dir=tmp_path / "work",
    )
    assert sel.ok
    assert sel.chosen_label == "agg2"
    assert sel.id_map == {"A": "agg1", "B": "agg2"}
    assert sel.chosen_id == "B"
    assert "reports the check" in sel.why
    assert sel.n_candidates == 2
    assert (tmp_path / "work" / "selection" / "agg2" / "selection.json").is_file()
    assert (tmp_path / "work" / "selection" / "agg2" / "candidates" / "A.md").is_file()
    assert (tmp_path / "work" / "selection" / "agg2" / "candidates" / "B.md").is_file()


def test_selector_failure_falls_back_within_the_pool(
    adapter: CodingAgentAdapter, tmp_path: Path
) -> None:
    one = adapter.execute("example", None, "agg1")
    candidates = {"agg1": _view(one, "agg1")}
    failing = _selector('"definitely-not-a-real-command-xyz"', tmp_path)
    sel = selection.run_selection(
        "example",
        2,
        "agg",
        candidates,
        adapter=adapter,
        prop=failing,
        work_dir=tmp_path / "work",
    )
    assert not sel.ok
    assert sel.error
    assert sel.dropped in ([], ["agg1"])


def test_assign_ids_is_stable_and_task_scoped() -> None:
    first = selection.assign_ids(["agg1", "agg2"], task_id="t1", k=2, mode="agg")
    again = selection.assign_ids(["agg1", "agg2"], task_id="t1", k=2, mode="agg")
    other = selection.assign_ids(["agg1", "agg2"], task_id="t2", k=2, mode="agg")
    assert first == again
    assert first != other
    assert set(first.values()) == {"agg1", "agg2"}
    assert first[selection._anon_id(0)] == "agg1"


def test_an_out_of_pool_choice_is_rejected(
    adapter: CodingAgentAdapter, tmp_path: Path
) -> None:
    one = adapter.execute("example", None, "agg1")
    bad = f'"{__import__("sys").executable}" "{Path(__file__).parent / "fixtures" / "bad_selector.py"}"'
    sel = selection.run_selection(
        "example",
        1,
        "agg",
        {"agg1": _view(one, "agg1")},
        adapter=adapter,
        prop=_selector(bad, tmp_path),
        work_dir=tmp_path / "work",
    )
    assert not sel.ok
    assert "which is not one of" in sel.error
