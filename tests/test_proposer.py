from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from impro.core.proposer import Proposer, ProposerError
from impro.core.spec import ChannelSpec, resolve_channel_model


def _proposer(cmd: str, tmp_path: Path, *, attempts: int = 1) -> Proposer:
    return Proposer(
        spec=ChannelSpec("command", "agent", command=cmd, timeout=60),
        audit_dir=tmp_path / "audit",
        attempts=attempts,
    )


def _workspace(tmp_path: Path) -> Path:
    ctx = tmp_path / "context-inv1"
    harness = ctx / "harness"
    harness.mkdir(parents=True)
    (harness / "guardrails.md").write_text("# Guardrails\n", encoding="utf-8")
    return ctx


def test_command_channel_edits_the_harness_and_harvests_it(
    tmp_path: Path, agent_cmd: str
) -> None:
    ctx = _workspace(tmp_path)
    proposer = _proposer(agent_cmd, tmp_path)
    reply = proposer.call(
        "Improve the harness.", ctx, "inv1.a1", harvest="context/harness"
    )
    assert reply.ok
    assert reply.workspace is not None
    body = (reply.workspace / "guardrails.md").read_text(encoding="utf-8")
    assert "run it before claiming the change works" in body
    assert reply.text.startswith("<notes>")
    assert reply.channel == "command"
    audit = tmp_path / "audit"
    assert any(audit.rglob("*"))


def test_a_second_identical_call_is_served_from_cache(
    tmp_path: Path, agent_cmd: str
) -> None:
    ctx = _workspace(tmp_path)
    proposer = _proposer(agent_cmd, tmp_path)
    first = proposer.call("Improve the harness.", ctx, "inv1.a1", harvest="context/harness")
    second = proposer.call("Improve the harness.", ctx, "inv1.a1", harvest="context/harness")
    assert first.ok and second.ok
    assert not first.cached
    assert second.cached
    assert first.workspace == second.workspace


def test_a_different_mission_misses_the_cache(tmp_path: Path, agent_cmd: str) -> None:
    ctx = _workspace(tmp_path)
    proposer = _proposer(agent_cmd, tmp_path)
    proposer.call("Improve the harness.", ctx, "inv1.a1", harvest="context/harness")
    second = proposer.call("Improve it differently.", ctx, "inv1.a1", harvest="context/harness")
    assert not second.cached


def test_an_empty_reply_is_an_error_not_an_empty_proposal(tmp_path: Path, monkeypatch) -> None:
    ctx = _workspace(tmp_path)
    monkeypatch.setattr("impro.core.proposer.time.sleep", lambda _s: None)
    cmd = f'"{subprocess.list2cmdline([__import__("sys").executable])}" -c "import sys; sys.exit(0)"'
    proposer = _proposer(cmd, tmp_path, attempts=2)
    with pytest.raises(ProposerError) as caught:
        proposer.call("Improve.", ctx, "inv1.a1", harvest="context/harness")
    assert caught.value.attempts == 2


def test_a_failing_command_is_an_error_not_a_silent_empty(tmp_path: Path) -> None:
    ctx = _workspace(tmp_path)
    cmd = f'"{subprocess.list2cmdline([__import__("sys").executable])}" -c "import sys; sys.exit(7)"'
    proposer = _proposer(cmd, tmp_path)
    with pytest.raises(ProposerError, match="rc=7"):
        proposer.call("Improve.", ctx, "inv1.a1")


def test_system_text_is_written_for_file_reading_agents(tmp_path: Path) -> None:
    ctx = _workspace(tmp_path)
    code = "from pathlib import Path; print(Path('HARNESS.md').read_text())"
    cmd = f'"{subprocess.list2cmdline([__import__("sys").executable])}" -c "{code}"'
    proposer = _proposer(cmd, tmp_path)
    reply = proposer.call("Mission.", ctx, "label", system="SYSTEM MARKER")
    assert "SYSTEM MARKER" in reply.text
    assert (tmp_path / "audit").is_dir()


def test_mission_file_placeholder_is_substituted(tmp_path: Path, agent_cmd: str) -> None:
    ctx = _workspace(tmp_path)
    code = (
        "import pathlib,sys; "
        "print(pathlib.Path(sys.argv[1]).read_text().splitlines()[-1])"
    )
    cmd = f'"{subprocess.list2cmdline([__import__("sys").executable])}" -c "{code}" "{{mission_file}}"'
    proposer = _proposer(cmd, tmp_path)
    reply = proposer.call("final line marker", ctx, "label")
    assert "final line marker" in reply.text


def test_resolve_command_channel_needs_a_command(monkeypatch) -> None:
    monkeypatch.setattr("impro.config.AGENT_CMD", "")
    with pytest.raises(ValueError, match="IMPRO_AGENT_CMD"):
        resolve_channel_model("command", None)
    spec = resolve_channel_model("command", None, command="my-agent -p")
    assert spec.command == "my-agent -p"
    assert spec.model == "agent"


def test_claude_channel_still_requires_a_paired_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "impro.config.PROPOSER_MODEL_BY_CHANNEL",
        {"claude_cli": "claude-sonnet-4", "opencode": "", "command": "agent"},
    )
    with pytest.raises(ValueError, match="TOGETHER"):
        resolve_channel_model(None, "claude-sonnet-4")
    assert resolve_channel_model("claude_cli", "claude-sonnet-4").model == "claude-sonnet-4"
