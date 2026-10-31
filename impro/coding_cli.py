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

"""The command line: init, show, tasks, run, domain, sweep, apply, lessons."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

from . import __version__, config
from .adapter import CodingAgentAdapter, make_adapter
from .core import library as library_store
from .core import schedule
from .core import tree as harness_tree
from .core.proposer import Proposer
from .substrate import CODING_SURFACE, base_tree

MODES = ("agg", "seq")


def _mode_list(value: str) -> tuple[str, ...]:
    if value == "both":
        return MODES
    if value in ("parallel", "agg"):
        return ("agg",)
    if value in ("sequential", "seq"):
        return ("seq",)
    raise SystemExit(f"unknown mode {value!r}; expected both, parallel or sequential")


def _proposers(adapter: CodingAgentAdapter, runs_root: Path) -> tuple[Proposer, Proposer]:
    audit = Path(runs_root) / "_audit"
    proposer = Proposer(
        spec=adapter.spec.channels["proposer"],
        audit_dir=audit,
        attempts=config.TRANSPORT_ATTEMPTS,
    )
    selector = Proposer(
        spec=adapter.spec.channels["selector"],
        audit_dir=audit,
        attempts=config.TRANSPORT_ATTEMPTS,
    )
    return proposer, selector


def _libraries(adapter: CodingAgentAdapter, library_root: Path, domain: str, modes: Sequence[str]):
    surface = adapter.substrate.surface()
    return {
        mode: library_store.Library(
            root=Path(library_root) / mode, domain=domain, surface=surface
        )
        for mode in modes
    }


def _adapter(args: argparse.Namespace) -> CodingAgentAdapter:
    return make_adapter(
        tasks_root=args.tasks,
        runs_root=args.runs,
        harness_root=args.harness,
        agent_cmd=args.agent,
        proposer_cmd=args.proposer,
        selector_cmd=args.selector,
        timeout=args.timeout,
    )


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--tasks",
        type=Path,
        default=Path(config.ROOT) / "tasks",
        help="task store root (default: <repo>/tasks)",
    )
    parser.add_argument(
        "--runs",
        type=Path,
        default=Path(config.RUNS),
        help="where run namespaces live (default: <repo>/runs)",
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path(config.RUNS) / "library",
        help="experience-library root (default: <runs>/library)",
    )
    parser.add_argument(
        "--harness",
        type=Path,
        default=Path(config.HARNESS),
        help="base harness tree (default: <repo>/harness)",
    )
    parser.add_argument("--agent", default=None, help="rollout command (default: IMPRO_AGENT_CMD)")
    parser.add_argument(
        "--proposer",
        default=None,
        help="harness-improver command (default: IMPRO_PROPOSER_CMD, then the rollout command)",
    )
    parser.add_argument(
        "--selector", default=None, help="selector command (default: IMPRO_SELECTOR_CMD)"
    )
    parser.add_argument("--timeout", type=int, default=20 * 60, help="per-session timeout in seconds")


def cmd_init(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    target = Path(args.harness).resolve()
    if not source.is_dir():
        print(f"no bundled harness at {source}", file=sys.stderr)
        return 2
    if target.exists() and any(target.iterdir()) and not args.force:
        print(f"{target} is not empty; pass --force to replace it", file=sys.stderr)
        return 2
    if target.exists() and args.force:
        shutil.rmtree(target)
    shutil.copytree(source, target)
    tree = base_tree(CODING_SURFACE, target)
    try:
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)
    except ValueError as exc:
        shutil.rmtree(target, ignore_errors=True)
        print(f"the bundled harness is invalid: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {len(tree)} files to {target}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    root = Path(args.harness).resolve()
    tree = base_tree(CODING_SURFACE, root)
    errors: list[str] = []
    try:
        harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)
    except ValueError as exc:
        errors.append(str(exc))
    always_on = sum(len(tree.get(rel, "")) for rel in CODING_SURFACE.always_on)
    census = {
        "root": str(root),
        "files": len(tree),
        "always_on_chars": always_on,
        "always_on_cap": CODING_SURFACE.always_on_max,
        "skills": harness_tree.skill_names(CODING_SURFACE, tree),
        "subagents": harness_tree.subagent_names(CODING_SURFACE, tree),
        "scripts": sorted(
            rel for rel in tree if rel.startswith("scripts/") and rel.endswith(".py")
        ),
        "valid": not errors,
    }
    if args.json:
        print(json.dumps({**census, "errors": errors}, indent=2))
    else:
        print(f"harness  {census['root']}")
        print(f"files    {census['files']}")
        print(f"always-on {always_on} / {CODING_SURFACE.always_on_max} chars")
        print(f"skills   {', '.join(census['skills']) or '-'}")
        print(f"subagents {', '.join(census['subagents']) or '-'}")
        print(f"scripts  {', '.join(census['scripts']) or '-'}")
        print("valid    yes" if not errors else "valid    NO")
        for error in errors:
            print(f"  {error}")
    return 0 if not errors else 1


def cmd_tasks(args: argparse.Namespace) -> int:
    # Listing tasks needs no model; only executing one does.
    args.agent = args.agent or config.AGENT_CMD or "unused"
    adapter = _adapter(args)
    for task_id in adapter.tasks("all"):
        print(f"{task_id}\t{adapter.domain_of(task_id)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    adapter = _adapter(args)
    modes = _mode_list(args.mode)
    runs_root = Path(args.runs)
    library_root = Path(args.library)
    proposer, selector = _proposers(adapter, runs_root)
    task = args.task
    result = schedule.run_task(
        task,
        args.k,
        adapter=adapter,
        prop=proposer,
        runs_root=runs_root,
        modes=modes,
        seed=args.seed,
        tag=args.tag,
        libraries=_libraries(adapter, library_root, adapter.domain_of(task), modes),
        selector_prop=selector,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"{task}: {result.status}")
        for mode in modes:
            record = result.modes.get(mode) or {}
            selection = result.selections.get(mode) or {}
            chosen = selection.get("chosen_label") or "-"
            print(f"  {mode:<4} {record.get('ok') and 'ok' or 'FAILED':<8} chose {chosen}")
            if selection.get("why"):
                print(f"       why: {selection['why']}")
            if selection.get("lesson"):
                print(f"       lesson: {selection['lesson']}")
        for error in result.errors:
            print(f"  error: {error}")
    return 0 if result.status in ("ok", "skipped") else 1


def cmd_domain(args: argparse.Namespace) -> int:
    adapter = _adapter(args)
    modes = _mode_list(args.mode)
    task_ids = [t for t in adapter.tasks("all") if adapter.domain_of(t) == args.domain]
    if not task_ids:
        print(f"no tasks in {args.domain!r}", file=sys.stderr)
        return 2
    proposer, selector = _proposers(adapter, Path(args.runs))
    out = schedule.run_domain(
        args.domain,
        task_ids,
        args.k,
        adapter=adapter,
        prop=proposer,
        runs_root=Path(args.runs),
        library_root=Path(args.library),
        modes=modes,
        seed=args.seed,
        tag=args.tag,
        selector_prop=selector,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0 if not out["failed"] else 1


def cmd_sweep(args: argparse.Namespace) -> int:
    adapter = _adapter(args)
    modes = _mode_list(args.mode)
    proposer, selector = _proposers(adapter, Path(args.runs))
    out = schedule.run_sweep(
        args.k,
        adapter=adapter,
        prop=proposer,
        runs_root=Path(args.runs),
        library_root=Path(args.library),
        split="all",
        modes=modes,
        seed=args.seed,
        tag=args.tag,
        domain_parallel=args.domain_parallel,
        only_domains=tuple(args.only_domain),
        only_tasks=tuple(args.only_task),
        selector_prop=selector,
        max_tasks=args.max_tasks,
    )
    print(json.dumps(out, indent=2, default=str))
    return 0 if not out.get("failed") else 1


def cmd_lessons(args: argparse.Namespace) -> int:
    domain_dir = library_store.domain_dir(args.domain)
    found = False
    for mode in _mode_list(args.mode):
        path = Path(args.library) / mode / domain_dir / "INDEX.md"
        if path.is_file():
            found = True
            print(f"# {mode}\n")
            print(path.read_text(encoding="utf-8"))
    if not found:
        print(f"no library entries for {args.domain!r}", file=sys.stderr)
        return 2
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    target = Path(args.harness).resolve()
    slug = args.task.replace("/", "__")
    candidates = sorted(
        Path(args.library).glob(f"*/**/harnesses/{slug}/harness"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print(f"no adopted harness for {args.task!r} under {args.library}", file=sys.stderr)
        return 2
    source = candidates[0]
    tree = harness_tree.read_tree(CODING_SURFACE, source)
    harness_tree.validate(CODING_SURFACE, tree, allow_subagents=True)
    if target.exists() and any(target.iterdir()) and not args.force:
        print(f"{target} is not empty; pass --force to replace it", file=sys.stderr)
        return 2
    if target.exists():
        shutil.rmtree(target)
    harness_tree.write_tree(CODING_SURFACE, tree, target)
    print(f"applied {source} -> {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="impro",
        description="SKT recursive harness improvement for coding agents.",
        epilog=(
            "Benchmark reproductions: adapt, judge, report, check, demo, setup, "
            "bridge. impro-buddy double recursion: buddy. SKT latent recursion: mas. "
            "Run `impro <command> --help` for one."
        ),
    )
    parser.add_argument("--version", action="version", version=f"impro {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="write the bundled starter harness")
    init.add_argument("--source", type=Path, default=Path(config.ROOT) / "harness")
    init.add_argument("--harness", type=Path, default=Path(config.HARNESS))
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    show = sub.add_parser("show", help="print the harness census and validate it")
    show.add_argument("--harness", type=Path, default=Path(config.HARNESS))
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=cmd_show)

    tasks = sub.add_parser("tasks", help="list task ids and their areas")
    _common(tasks)
    tasks.set_defaults(func=cmd_tasks)

    run = sub.add_parser("run", help="run one task through the method")
    run.add_argument("task")
    run.add_argument("--k", type=int, default=1, help="reference/candidate rollouts per step")
    run.add_argument(
        "--mode", default="both", help="both, parallel (agg) or sequential (seq)"
    )
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--tag", default="")
    run.add_argument("--json", action="store_true")
    _common(run)
    run.set_defaults(func=cmd_run)

    domain = sub.add_parser("domain", help="run every task in one area, threading the library")
    domain.add_argument("domain")
    domain.add_argument("--k", type=int, default=1)
    domain.add_argument("--mode", default="both")
    domain.add_argument("--seed", type=int, default=None)
    domain.add_argument("--tag", default="")
    _common(domain)
    domain.set_defaults(func=cmd_domain)

    sweep = sub.add_parser("sweep", help="run every area")
    sweep.add_argument("--k", type=int, default=1)
    sweep.add_argument("--mode", default="both")
    sweep.add_argument("--seed", type=int, default=None)
    sweep.add_argument("--tag", default="")
    sweep.add_argument("--domain-parallel", type=int, default=1)
    sweep.add_argument("--only-domain", action="append", default=[])
    sweep.add_argument("--only-task", action="append", default=[])
    sweep.add_argument("--max-tasks", type=int, default=None)
    _common(sweep)
    sweep.set_defaults(func=cmd_sweep)

    lessons = sub.add_parser("lessons", help="print the experience library for an area")
    lessons.add_argument("--domain", required=True)
    lessons.add_argument("--library", type=Path, default=Path(config.RUNS) / "library")
    lessons.add_argument("--mode", default="both")
    lessons.set_defaults(func=cmd_lessons)

    apply = sub.add_parser("apply", help="install an adopted harness as the base harness")
    apply.add_argument("task")
    apply.add_argument("--library", type=Path, default=Path(config.RUNS) / "library")
    apply.add_argument("--harness", type=Path, default=Path(config.HARNESS))
    apply.add_argument("--force", action="store_true")
    apply.set_defaults(func=cmd_apply)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (config.ConfigError, FileNotFoundError, ValueError) as exc:
        print(f"impro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
