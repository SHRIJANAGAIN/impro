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

"""The coding-agent adapter: the whole outside world the method needs.

A task is a directory with a ``TASK.md`` and an optional ``source/`` tree. A
rollout copies that source, renders the candidate harness into the prompt, and
runs any agent command that follows the stdin/stdout contract. The changed
files and the agent's report are the deliverable; no judge is involved.

    tasks/<area>/<task>/TASK.md
    tasks/<area>/<task>/source/...

Everything else is the method in `impro.core`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import config
from .core import tree as harness_tree
from .core.spec import BenchPrompts, BenchSpec, ChannelSpec, RunView
from .substrate import CODING_SURFACE, base_tree, render

#: Copied into a rollout but never counted as its deliverable.
SKIP_DIRS = frozenset({".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"})

#: A rollout may report at most this many changed files, each at most this big.
MAX_FILES = 24
MAX_FILE_BYTES = 200_000

#: How much of the agent's output is kept in one trajectory.
OBS_TRUNC = 50_000


CODING_PROMPTS = BenchPrompts(
    work="a request to change a repository, made in the user's own words",
    domain_word="area",
    inv_levers="\n".join(
        [
            "- DISCOVERY: how the agent finds the right file before writing.",
            "- VERIFICATION: which check falsifies the change, and how narrow it is.",
            "- RECOVERY: what to do after a failed command, and when to stop repeating it.",
            "- BOUNDED WORK: how the agent keeps a large change reviewable.",
            "- COMPLETION: how the agent knows it is done, and what it must report.",
            "- SAFETY: when to stop and ask instead of guessing.",
        ]
    ),
    dom_levers="\n".join(
        [
            "- THE ASK: what the user wants to be true, and the scope they did not ask for.",
            "- REPOSITORY CONVENTIONS: naming, structure, error handling, test style.",
            "- CONTROLLING SOURCES: the code, schema, docs and config that decide a claim.",
            "- COMPATIBILITY: public APIs, migrations, callers that cannot break.",
            "- THE CHANGE: the files that must move together for the request to hold.",
            "- AUDIENCE: who reviews the change, and what they need in the summary.",
        ]
    ),
    deliverable_word="change",
    prompt_pack="adapt",
)


@dataclass(frozen=True)
class CodingSubstrate:
    """The substrate the core sees: a name and one surface value."""

    name: str = "workspace"

    def surface(self) -> harness_tree.SurfaceSpec:
        return CODING_SURFACE


@dataclass
class CodingAgentAdapter:
    """A task store plus one agent command. Implements `BenchmarkAdapter`."""

    tasks_root: Path
    runs_root: Path
    harness_root: Path
    agent_cmd: str
    proposer_cmd: str | None = None
    selector_cmd: str | None = None
    domain_default: str = "general"
    timeout: int = 20 * 60
    task_source: str | None = None
    leak_globs: tuple[str, ...] = ()
    substrate: CodingSubstrate = CodingSubstrate()

    def __post_init__(self) -> None:
        self.tasks_root = Path(self.tasks_root).expanduser().resolve()
        self.runs_root = Path(self.runs_root).expanduser().resolve()
        self.harness_root = Path(self.harness_root).expanduser().resolve()
        if not self.tasks_root.is_dir():
            raise FileNotFoundError(f"no tasks directory at {self.tasks_root}")
        if not self.agent_cmd.strip():
            raise ValueError("agent_cmd must not be empty")
        self.spec = BenchSpec(
            name="impro",
            runs_root=self.runs_root,
            install_mode="workspace_agents_md",
            prompts=CODING_PROMPTS,
            channels={
                "proposer": ChannelSpec(
                    "command",
                    "agent",
                    timeout=self.timeout,
                    command=self.proposer_cmd or self.agent_cmd,
                ),
                "selector": ChannelSpec(
                    "command",
                    "agent",
                    timeout=self.timeout,
                    command=self.selector_cmd or self.agent_cmd,
                ),
            },
            domain_word="area",
            allow_subagents=True,
            reserved_scripts=harness_tree.RESERVED_SCRIPTS,
            leak_globs=self.leak_globs,
            proposer_deliverables="contents",
            state_deliverable=True,
            obs_trunc=OBS_TRUNC,
        )

    # -- tasks ---------------------------------------------------------

    def _task_dir(self, task_id: str) -> Path:
        path = (self.tasks_root / task_id).resolve()
        if self.tasks_root not in path.parents:
            raise ValueError(f"task id escapes the task root: {task_id!r}")
        return path

    def tasks(self, split: str = "all") -> list[str]:
        if split not in ("all", "train"):
            raise ValueError(f"unknown split {split!r}; this adapter has one split, 'all'")
        found: list[str] = []
        for task_md in sorted(self.tasks_root.rglob("TASK.md")):
            relative = task_md.parent.relative_to(self.tasks_root).as_posix()
            found.append(relative)
        return found

    def domain_of(self, task_id: str) -> str:
        head, sep, _ = task_id.partition("/")
        return head if sep else self.domain_default

    def task_prompt(self, task_id: str) -> str:
        path = self._task_dir(task_id) / "TASK.md"
        if not path.is_file():
            raise FileNotFoundError(f"no TASK.md for {task_id!r} at {path}")
        return path.read_text(encoding="utf-8")

    def task_files(self, task_id: str) -> Path | None:
        src = self._task_dir(task_id) / "source"
        return src if src.is_dir() else None

    # -- harness -------------------------------------------------------

    def base_harness(self) -> Path:
        return self.harness_root

    def validate_tree(self, tree: dict[str, str]) -> None:
        harness_tree.validate(
            CODING_SURFACE,
            tree,
            allow_subagents=self.spec.allow_subagents,
            reserved_scripts=self.spec.reserved_scripts,
        )

    # -- rollouts ------------------------------------------------------

    def execute(
        self,
        task_id: str,
        harness_dir: Path | None,
        run_id: str,
        *,
        timeout: int | None = None,
    ) -> Path:
        """Run the agent once in its own copy of the source; idempotent by run_id."""
        safe_task = re.sub(r"[^A-Za-z0-9_.-]+", "__", task_id)
        run_dir = self.runs_root / safe_task / "runs" / _safe(run_id)
        marker = run_dir / ".impro" / "run.json"
        if marker.is_file():
            return run_dir
        run_dir.mkdir(parents=True, exist_ok=True)

        source = self.task_files(task_id)
        before = _copy_source(source, run_dir) if source else {}
        harness = Path(harness_dir) if harness_dir else self.harness_root
        tree = base_tree(CODING_SURFACE, harness)
        block = render(CODING_SURFACE, tree)
        (run_dir / ".impro").mkdir(parents=True, exist_ok=True)
        harness_tree.write_tree(CODING_SURFACE, tree, run_dir / ".impro" / "harness")
        (run_dir / ".impro" / "harness.md").write_text(block, encoding="utf-8")

        prompt = f"{block}\n\n# TASK\n\n{self.task_prompt(task_id)}\n"
        started = time.time()
        error = ""
        rc = 0
        try:
            stdout, stderr, rc = _run_agent(
                self.agent_cmd,
                run_dir,
                prompt,
                timeout or self.timeout,
                label=f"rollout:{run_id}",
            )
        except subprocess.TimeoutExpired:
            stdout, stderr, rc = "", f"timeout after {timeout or self.timeout}s", 124
            error = stderr
        except Exception as exc:  # a broken command is a failed rollout, not a crash
            stdout, stderr, rc = "", f"{type(exc).__name__}: {exc}", 1
            error = stderr

        changed = _changed_files(before, run_dir)
        deliverable = _cap_files({rel: _read(run_dir / rel) for rel in changed})
        report = stdout.strip()
        (run_dir / ".impro" / "deliverable.md").write_text(report, encoding="utf-8")
        (run_dir / ".impro" / "files").mkdir(parents=True, exist_ok=True)
        for rel, body in deliverable.items():
            target = run_dir / ".impro" / "files" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        transcript = _transcript(self.agent_cmd, stdout, stderr, rc)
        (run_dir / ".impro" / "transcript.md").write_text(transcript, encoding="utf-8")
        (run_dir / ".impro" / "agent.log").write_text(
            f"$ {self.agent_cmd}\n\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
            encoding="utf-8",
        )
        if rc != 0 and not error:
            error = f"agent exited {rc}"
        marker.write_text(
            json.dumps(
                {
                    "task": task_id,
                    "runId": run_id,
                    "ok": rc == 0,
                    "delivered": bool(deliverable or report),
                    "rc": rc,
                    "error": error,
                    "wallS": round(time.time() - started, 1),
                    "harness": harness_tree.diff_summary(
                        CODING_SURFACE,
                        base_tree(CODING_SURFACE, self.harness_root),
                        tree,
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return run_dir

    # -- what the method reads ----------------------------------------

    def delivered(self, run_dir: Path) -> bool:
        meta = _meta(run_dir)
        if meta.get("delivered") is True:
            return True
        return bool(_deliverable_files(run_dir))

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        path = Path(run_dir) / ".impro" / "transcript.md"
        if not path.is_file():
            return "(no trajectory recorded)"
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:obs_trunc] if obs_trunc > 0 else ""

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        return _deliverable_files(run_dir)

    def deliverable_text(self, run_dir: Path) -> str:
        path = Path(run_dir) / ".impro" / "deliverable.md"
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    def score(self, run_dir: Path, task_id: str) -> dict | None:
        """This build has no judge. `judge.py` is present for benchmark users only."""
        return None

    def view(self, task_id: str, label: str, run_id: str, run_dir: Path) -> RunView:
        """A RunView for a finished rollout, with the failure surfaced."""
        meta = _meta(run_dir)
        return RunView(
            label=label,
            run_id=run_id,
            run_dir=Path(run_dir),
            ok=meta.get("ok") is not False,
            delivered=self.delivered(Path(run_dir)),
            cost_usd=0.0,
            wall_s=float(meta.get("wallS") or 0.0),
            error=str(meta.get("error") or ""),
        )


# -- helpers -----------------------------------------------------------


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("._") or "run"


def _run_agent(
    command: str, cwd: Path, prompt: str, timeout: int, *, label: str
) -> tuple[str, str, int]:
    """Run one agent command with the prompt on stdin, its workspace as cwd."""
    mission = cwd / "MISSION.md"
    mission.write_text(prompt, encoding="utf-8")
    rendered = command
    for token, value in (("{mission_file}", mission), ("{workspace}", cwd)):
        rendered = rendered.replace(token, f'"{value}"')
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    env["IMPRO_RUN_DIR"] = str(cwd)
    env["IMPRO_LABEL"] = label
    proc = subprocess.run(
        rendered,
        shell=True,
        input=prompt,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.stdout or "", proc.stderr or "", proc.returncode


def _copy_source(source: Path, run_dir: Path) -> dict[str, str]:
    """Copy the source tree in; return hashes of every file before the agent runs."""
    before: dict[str, str] = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source).as_posix()
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        target = run_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        before[rel] = _hash(target)
    return before


def _changed_files(before: dict[str, str], run_dir: Path) -> list[str]:
    """Files added or modified by the agent, outside the harness's own directory."""
    changed: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel in ("MISSION.md", "HARNESS.md"):
            continue
        if rel.startswith(".impro/") or any(part in SKIP_DIRS for part in path.parts):
            continue
        if before.get(rel) != _hash(path):
            changed.append(rel)
    return changed


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _cap_files(files: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in sorted(files):
        body = files[rel]
        if len(body) > MAX_FILE_BYTES:
            body = body[:MAX_FILE_BYTES] + "\n[truncated by impro]\n"
        out[rel] = body
        if len(out) >= MAX_FILES:
            break
    return out


def _transcript(command: str, stdout: str, stderr: str, rc: int) -> str:
    parts = [
        "[ACTION] agent",
        f"[OBSERVATION] command: {command}",
        f"[ASSISTANT] {stdout.strip() or '(no report)'}",
    ]
    if stderr.strip():
        parts.append(f"[OBSERVATION ERROR] {stderr.strip()}")
    parts.append(f"[OBSERVATION] exit {rc}")
    return "\n\n".join(parts) + "\n"


def _meta(run_dir: Path) -> dict:
    path = Path(run_dir) / ".impro" / "run.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _deliverable_files(run_dir: Path) -> dict[str, str]:
    root = Path(run_dir) / ".impro" / "files"
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = _read(path)
    return out


def make_adapter(
    *,
    tasks_root: Path | str,
    runs_root: Path | str | None = None,
    harness_root: Path | str | None = None,
    agent_cmd: str | None = None,
    proposer_cmd: str | None = None,
    selector_cmd: str | None = None,
    timeout: int = 20 * 60,
) -> CodingAgentAdapter:
    """Build the adapter from explicit values or the environment."""
    return CodingAgentAdapter(
        tasks_root=Path(tasks_root),
        runs_root=Path(runs_root or config.RUNS),
        harness_root=Path(harness_root or config.HARNESS),
        agent_cmd=agent_cmd or config.AGENT_CMD,
        proposer_cmd=proposer_cmd or config.env("IMPRO_PROPOSER_CMD"),
        selector_cmd=selector_cmd or config.env("IMPRO_SELECTOR_CMD"),
        timeout=timeout,
    )


__all__ = [
    "CODING_PROMPTS",
    "CodingAgentAdapter",
    "CodingSubstrate",
    "MAX_FILES",
    "MAX_FILE_BYTES",
    "OBS_TRUNC",
    "make_adapter",
]
