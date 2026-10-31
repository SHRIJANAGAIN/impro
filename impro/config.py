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

"""Deployment settings and dependency versions. Shell values override .env.

This module serves both halves of the package:

* the agent-agnostic coding method (``impro.agent`` / ``impro.coding_cli``),
  where the only required setting is ``IMPRO_AGENT_CMD``; and
* the benchmark reproductions under ``impro.benchmarks``, which retain the
  upstream OpenCode/Codex/Vertex settings.

``IMPRO_*`` is the primary environment namespace. The legacy upstream
``HARNESS2_*`` names still work as fallbacks, so an upstream ``.env`` can be
reused unchanged. SKT-branded Vertex aliases take precedence over the
functional Google Cloud names.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
ROOT = PKG.parent if (PKG.parent / "pyproject.toml").is_file() else Path.cwd()
THIRD_PARTY = ROOT / "third_party"
METHOD_VERSION = 2

DEPENDENCIES = ROOT / "dependencies"


class ConfigError(RuntimeError):
    """A required deployment value is missing; the message carries the remediation."""


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Load KEY=VALUE lines into os.environ with setdefault (the shell wins).

    Accepts blank lines, ``#`` comments, an optional ``export `` prefix, and
    single- or double-quoted values. A missing or unreadable file is not an
    error.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or not all(c.isalnum() or c == "_" for c in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)


load_dotenv()


def _legacy_name(name: str) -> str | None:
    if name.startswith("IMPRO_"):
        return "HARNESS2_" + name[len("IMPRO_") :]
    return None


def env(name: str, default=None):
    """Env override where a set-but-empty variable is the same as an unset one.

    ``IMPRO_*`` wins; ``HARNESS2_*`` is accepted as a compatibility fallback.
    """
    value = os.environ.get(name)
    if not value:
        legacy = _legacy_name(name)
        if legacy is not None:
            value = os.environ.get(legacy)
    return value or default


def _first_env(*names: str) -> str:
    """The first non-empty value among ``names``, or an empty string."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def env_int(name: str, default: int) -> int:
    v = env(name)
    if v is None:
        return int(default)
    try:
        return int(v)
    except ValueError as e:
        raise ConfigError(f"{name} must be an integer, got {v!r}") from e


def require(name: str, *, needed_by: str) -> str:
    """The value of ``name``, or ConfigError with the remediation line."""
    v = env(name)
    if not v:
        raise ConfigError(
            f"{name} is required for {needed_by}; set it in .env or the shell "
            f"(see .env.example)"
        )
    return str(v)


# -- agent-agnostic coding surface -------------------------------------

RUNS = Path(env("IMPRO_RUNS_DIR", ROOT / "runs")).expanduser().resolve()
HARNESS = Path(env("IMPRO_HARNESS", ROOT / "harness")).expanduser().resolve()

# An empty command is allowed at import time (tests and `init`/`show` do not
# need a model); it is required when a session runs.
AGENT_CMD = env("IMPRO_AGENT_CMD", "")
PROPOSER_CMD = env("IMPRO_PROPOSER_CMD", "")
SELECTOR_CMD = env("IMPRO_SELECTOR_CMD", "")


# -- models and endpoints ------------------------------------------------

VERTEX_PROJECT = _first_env(
    "SKT_VERTEX_PROJECT",
    "IMPRO_VERTEX_PROJECT",
    "HARNESS2_VERTEX_PROJECT",
    "GOOGLE_CLOUD_PROJECT",
)
VERTEX_REGION = _first_env(
    "SKT_VERTEX_LOCATION",
    "IMPRO_VERTEX_LOCATION",
    "HARNESS2_VERTEX_LOCATION",
    "GOOGLE_CLOUD_LOCATION",
) or "global"
if VERTEX_PROJECT:
    os.environ.setdefault("SKT_VERTEX_PROJECT", VERTEX_PROJECT)
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", VERTEX_PROJECT)
os.environ.setdefault("SKT_VERTEX_LOCATION", VERTEX_REGION)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", VERTEX_REGION)

SOLVER_MODEL_OC = env("IMPRO_SOLVER_MODEL", "")
SOLVER_MODEL_CX = env("IMPRO_CODEX_MODEL", SOLVER_MODEL_OC.split("/", 1)[-1])
IMPROVER_MODEL = env("IMPRO_IMPROVER_MODEL", SOLVER_MODEL_OC)
JUDGE_MODEL = env("IMPRO_JUDGE_MODEL", "")

DEPENDENCY_PINS = {
    "job-bench-eval": "fa03a17f9ff662f136798a274e10011c3aa00fd0",
    "workbuddy-bench": "b516950be5b56eb3be406c2f76ee1c5111dcb57f",
    "harvey-labs": "b58a28ae9fde5ee4b810e53b4fd0a1915325a35d",
    "opencode": "23fb5e0516c99ac04a1aa46c193efda2e1b9bb24",
}
DEPENDENCY_ORIGINS = {
    "job-bench-eval": "https://github.com/Job-Bench/job-bench-eval.git",
    "workbuddy-bench": "https://github.com/Tencent/workbuddy-bench.git",
    "harvey-labs": "https://github.com/harveyai/harvey-labs.git",
    "opencode": "https://github.com/anomalyco/opencode.git",
}


def jb_repo() -> Path:
    return DEPENDENCIES / "job-bench-eval"


def wb_repo() -> Path:
    return DEPENDENCIES / "workbuddy-bench"


def lab_repo() -> Path:
    return DEPENDENCIES / "harvey-labs"


OPENCODE_DIR = DEPENDENCIES / "opencode"
_BUN_NAME = "bun.exe" if os.name == "nt" else "bun"
BUN = DEPENDENCIES / "tools" / "node_modules" / ".bin" / _BUN_NAME
_VENV_BIN = "Scripts" if os.name == "nt" else "bin"
_PYTHON_NAME = "python.exe" if os.name == "nt" else "python"
LAB_PYTHON = lab_repo() / ".venv" / _VENV_BIN / _PYTHON_NAME
WB_PYTHON = wb_repo() / ".venv" / _VENV_BIN / _PYTHON_NAME
LAB_JUDGE_MODEL = (
    "vertex/" + JUDGE_MODEL if JUDGE_MODEL.startswith(("claude", "gemini")) else JUDGE_MODEL
)
LAB_DELIV_CAP = 60000
JB_JUDGE_PYTHON = jb_repo() / ".venv" / _VENV_BIN / _PYTHON_NAME
JB_JUDGE_MODEL = (
    "google/" + JUDGE_MODEL
    if JUDGE_MODEL.startswith("gemini") and not env("IMPRO_JUDGE_BASE_URL")
    else JUDGE_MODEL
)
_vertex_host = (
    "aiplatform.googleapis.com"
    if VERTEX_REGION == "global"
    else f"{VERTEX_REGION}-aiplatform.googleapis.com"
)
VERTEX_OPENAI_URL = (
    f"https://{_vertex_host}/v1/projects/{VERTEX_PROJECT}"
    f"/locations/{VERTEX_REGION}/endpoints/openapi"
)
JB_JUDGE_API_BASE = env("IMPRO_JUDGE_BASE_URL", VERTEX_OPENAI_URL if VERTEX_PROJECT else "")
JB_JUDGE_API_KEY = env("IMPRO_JUDGE_API_KEY", "")
JB_JUDGE_REASONING_EFFORT = "low"
JB_REPORTING_JUDGE_DETAILS = ""
JB_OBS_TRUNC = 50000

CODEX_VERSION = "0.144.6"
CODEX_DIST = str(DEPENDENCIES / "codex" / "dist")
CODEX_BIN = Path(CODEX_DIST) / ("codex.exe" if os.name == "nt" else "codex")
CODEX_BASE_URL = env("IMPRO_CODEX_BASE_URL", "")
CODEX_CONTAINER_URL = env("IMPRO_CODEX_CONTAINER_URL", CODEX_BASE_URL)
VERTEX_PROXY_KEY = env("IMPRO_CODEX_API_KEY", "")
CODEX_HOME_DIR = DEPENDENCIES / "codex" / "home"

WB_SOLVER_MODEL = "impro/solver"
WB_WEB_JUDGE = "impro/judge"
WB_RENDER_PY = sys.executable
WB_OC_HARNESS_VER = "1.14.18"
WB_CX_HARNESS_VER = CODEX_VERSION
WB_MAX_JOBS = {"oc": 1, "cx": 1}
WB_MAX_TRIALS = {"oc": 2, "cx": 2}
WB_MODEL_CONNECTION = "local_proxy"

# The benchmark channels keep the upstream default. The coding adapter builds
# an explicit ``command`` ChannelSpec and does not depend on this value.
DEFAULT_PROPOSER_CHANNEL = env("IMPRO_PROPOSER_CHANNEL", "opencode")
PROPOSER_MODEL_BY_CHANNEL = {
    "opencode": IMPROVER_MODEL,
    "claude_cli": IMPROVER_MODEL,
    "command": "agent",
}
PHASE_WIDTH = env_int("IMPRO_PHASE_WIDTH", 2)
TRANSPORT_ATTEMPTS = env_int("IMPRO_TRANSPORT_ATTEMPTS", 2)
PROPOSER_CONCURRENCY = env_int("IMPRO_PROPOSER_CONCURRENCY", 2)


def validate_models(*, judge: bool = False) -> None:
    """Fail early with the one setting a run actually needs."""
    if DEFAULT_PROPOSER_CHANNEL == "command":
        if not AGENT_CMD.strip():
            raise ConfigError(
                "IMPRO_AGENT_CMD is required for the command channel; point it at "
                "an agent that reads a prompt on stdin (e.g. 'claude -p')"
            )
        if judge:
            require("IMPRO_JUDGE_MODEL", needed_by="benchmark judging")
        return
    require("IMPRO_SOLVER_MODEL", needed_by="executor rollouts")
    if "/" not in SOLVER_MODEL_OC or "/" not in IMPROVER_MODEL:
        raise ConfigError("Executor and improver models must use OpenCode's provider/model syntax")
    if any(m.startswith("google-vertex") for m in (SOLVER_MODEL_OC, IMPROVER_MODEL)):
        if not VERTEX_PROJECT:
            raise ConfigError(
                "Set SKT_VERTEX_PROJECT (or GOOGLE_CLOUD_PROJECT) for Vertex AI"
            )
    if judge:
        require("IMPRO_JUDGE_MODEL", needed_by="benchmark judging")
