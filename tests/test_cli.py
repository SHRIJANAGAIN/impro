from __future__ import annotations

import json
from pathlib import Path

from impro import cli
from impro.core import tree as harness_tree
from impro.core.library import Library
from impro.substrate import CODING_SURFACE, base_tree


def test_show_prints_the_census(repo: Path, capsys) -> None:
    code = cli.main(["show", "--harness", str(repo / "harness"), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["skills"] == ["verify-change"]
    assert payload["always_on_chars"] > 0


def test_show_fails_a_broken_harness(repo: Path, tmp_path: Path, capsys) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["scripts/broken.py"] = "def broken(:\n"
    harness_tree.write_tree(CODING_SURFACE, tree, tmp_path / "harness")
    code = cli.main(["show", "--harness", str(tmp_path / "harness"), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is False
    assert any("does not compile" in error for error in payload["errors"])


def test_tasks_works_without_a_configured_agent(repo: Path, capsys) -> None:
    code = cli.main(
        [
            "tasks",
            "--tasks",
            str(repo / "tasks"),
            "--runs",
            str(repo / "runs"),
            "--library",
            str(repo / "library"),
            "--harness",
            str(repo / "harness"),
        ]
    )
    assert code == 0
    assert "example\tgeneral" in capsys.readouterr().out


def test_init_writes_a_valid_tree_and_refuses_to_overwrite(
    repo: Path, tmp_path: Path, capsys
) -> None:
    target = tmp_path / "harness"
    assert (
        cli.main(
            [
                "init",
                "--source",
                str(repo / "harness"),
                "--harness",
                str(target),
            ]
        )
        == 0
    )
    assert (target / "systemprompt.md").is_file()
    assert cli.main(["init", "--source", str(repo / "harness"), "--harness", str(target)]) == 2
    assert (
        cli.main(
            [
                "init",
                "--source",
                str(repo / "harness"),
                "--harness",
                str(target),
                "--force",
            ]
        )
        == 0
    )
    assert "wrote" in capsys.readouterr().out


def test_lessons_and_apply_read_a_stored_harness(repo: Path, tmp_path: Path, capsys) -> None:
    tree = dict(base_tree(CODING_SURFACE, repo / "harness"))
    tree["memory.md"] = "A lesson worth carrying.\n"
    library = Library(
        root=tmp_path / "library" / "agg",
        domain="area",
        surface=CODING_SURFACE,
    )
    library.add(
        "area/t1",
        tree,
        label="agg1",
        experience={
            "cue": "a task with one obvious edit",
            "lesson": "carry the lesson in memory.md",
            "evidence": "the adopted rollout proved it",
        },
    )
    code = cli.main(
        [
            "lessons",
            "--domain",
            "area",
            "--library",
            str(tmp_path / "library"),
            "--mode",
            "parallel",
        ]
    )
    assert code == 0
    assert "a task with one obvious edit" in capsys.readouterr().out

    target = tmp_path / "installed"
    code = cli.main(
        [
            "apply",
            "area/t1",
            "--library",
            str(tmp_path / "library"),
            "--harness",
            str(target),
        ]
    )
    assert code == 0
    assert (target / "memory.md").read_text(encoding="utf-8") == "A lesson worth carrying.\n"
    assert cli.main(["show", "--harness", str(target)]) == 0


def test_benchmark_subcommands_dispatch_to_their_upstream_cli(monkeypatch) -> None:
    from impro.cli import demo as demo_cli

    seen: list[str] = []

    def fake_main(argv):
        seen.extend(argv)
        return 7

    monkeypatch.setattr(demo_cli, "main", fake_main)
    assert cli.main(["demo", "--k", "1"]) == 7
    assert seen == ["--k", "1"]

def test_buddy_dispatch_reaches_the_scientific_method(monkeypatch) -> None:
    from impro.buddy import cli as buddy_cli

    seen: list[str] = []

    def fake_main(argv):
        seen.extend(argv)

    monkeypatch.setattr(buddy_cli, "main", fake_main)
    assert cli.main(["buddy", "preflight"]) == 0
    assert seen == ["preflight"]

def test_mas_dispatch_reaches_the_skt_method(monkeypatch) -> None:
    from impro.mas import cli as mas_cli

    seen: list[str] = []

    def fake_main(argv):
        seen.extend(argv)

    monkeypatch.setattr(mas_cli, "main", fake_main)
    assert cli.main(["mas", "infer", "--style", "sequential_light"]) == 0
    assert seen == ["infer", "--style", "sequential_light"]
