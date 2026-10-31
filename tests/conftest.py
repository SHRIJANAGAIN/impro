from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from impro.adapter import CodingAgentAdapter  # noqa: E402
from impro.substrate import CODING_SURFACE  # noqa: E402


@pytest.fixture(scope="session")
def repo() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def surface():
    return CODING_SURFACE


@pytest.fixture(scope="session")
def agent_cmd() -> str:
    return f'"{sys.executable}" "{ROOT / "tests" / "fixtures" / "agent.py"}"'


@pytest.fixture(scope="session")
def selector_cmd() -> str:
    return f'"{sys.executable}" "{ROOT / "tests" / "fixtures" / "selector.py"}"'


@pytest.fixture
def adapter(tmp_path: Path, agent_cmd: str, selector_cmd: str) -> CodingAgentAdapter:
    return CodingAgentAdapter(
        tasks_root=ROOT / "tasks",
        runs_root=tmp_path / "runs",
        harness_root=ROOT / "harness",
        agent_cmd=agent_cmd,
        selector_cmd=selector_cmd,
        timeout=120,
    )
