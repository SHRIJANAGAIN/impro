the harness for the next step. It doesn't just run an agent — it *improves the
harness the agent runs in*, one task at a time.

> **SKT** is the product name. `impro` is the package and CLI. Both work.

Built on the design of **Google Harness 2**, with the agent-experiment platform
of **ScienceBuddy** and the latent-space multi-agent recursion of
**RecursiveMAS** ported in-tree as first-class packages. Full attribution in
[`NOTICE`](NOTICE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

## Why

Most agent harnesses are static: same prompt, same tools, same loop, every run.
The failures repeat. `impro` treats the harness as the thing to optimize:

- **Parallel rollouts** — run *k* candidates per step, not one.
- **Selection** — a judge picks the winning trajectory, not a coin flip.
- **Experience library** — each win is distilled into a `cue → lesson → evidence`
  record that outlives the run.
- **Harness application** — adopted lessons become the base harness for the
  next task. Improvement compounds.

Modes: **parallel/aggregate** (`agg`) and **sequential** (`seq`) — run candidates
side-by-side or thread them through a chain, whichever fits the task.

---

## Install

```bash
pip install .              # core harness
pip install ".[buddy]"     # + ScienceBuddy experiment platform
pip install ".[mas]"       # + RecursiveMAS latent recursion (GPU-recommended)
pip install ".[test]"      # + pytest, ruff
```

Python ≥ 3.12. Core has **zero required dependencies** — the heavy stacks are
opt-in extras.

---

## Quickstart

```bash
impro init                                  # write the starter harness
impro tasks                                 # list tasks and areas
impro run <task> --k 4 --mode both          # one task, 4 rollouts, both modes
impro domain <area>                         # every task in an area
impro sweep                                 # every area
impro lessons --domain <area>               # inspect the experience library
impro apply <task>                          # install adopted lessons as base harness
```

Everything emits `--json` for scripting, and every path (tasks, runs, library,
harness) is overridable — `impro run --help` shows them all.

> `skt` is a synonym for `impro`. So is the `impro.exe` entry point.

---

## The three engines

`impro` is one install, three lineages:

| Engine | CLI | What it does | Upstream |
|---|---|---|---|
| **Core harness** | `impro`, `skt` | Recursive rollout → selection → lessons → apply | [Harness 2](https://github.com/) (Apache-2.0) |
| **Experiment platform** | `impro-buddy` | Multi-framework benchmarks, Ray-distributed training, run configs + HTML reports | ScienceBuddy (MIT) |
| **Latent recursion** | `impro-mas` | Sequential / mixture / distillation / deliberation multi-agent inference & GRPO training | RecursiveMAS (MIT) |

### Core — recursive harness (`impro.core`)

The loop: `spec → schedule → rollout → selection → ledger → library → proposer`.
Each stage is a module (`recursion.py`, `selection.py`, `library.py`,
`proposer.py`, ...), so you can swap the agent, proposer, or selector
independently via `--agent`, `--proposer`, `--selector`.

### Experiments — `impro.buddy`

Benchmark reproduction and agent evaluation: dataset-driven runs, multi-backend
serving, distributed training, structured configs, and auto-generated reports.

```bash
impro-buddy --help
impro-buddy-experiment --help
```

### Latent recursion — `impro.mas`

Multi-agent reasoning that recurses in latent space rather than in prompt
tokens — sequential, mixture, distillation, and deliberation modes, plus a GRPO
trainer with inner/outer loops.

```bash
impro-mas infer ...            # multi-agent inference
impro-mas-train-inner ...      # GRPO inner loop
impro-mas-train-outer ...      # GRPO outer loop
```

Requires `.[mas]` (torch, transformers, datasets). Ships a bundled MedQA
evaluation set.

---

## Benchmarks

The `impro-adapt` / `impro-judge` / `impro-report` / `impro-check` / `impro-demo` /
`impro-setup` / `impro-bridge` commands reproduce standard agent benchmarks —
adapt a task, judge the trajectory, generate the report. `impro-bridge` exposes
an OpenAI-compatible proxy fronting the harness.

---

## Does the orchestration actually help?

We ran a paired A/B on this question rather than assume the answer —
100 MedQA questions, strong reasoning model, with and without the
orchestration techniques.

**On a strong model: no.** A single call (94%) beat every orchestrated
condition — self-refinement (91%), self-consistency voting (93%), and both
combined (92%) — all at 3–8× the cost per question, none statistically
significant. Self-refinement *broke* more answers than it fixed.

This matches the literature: orchestration lifts **weak** base models, where
there's headroom to recover. On a model that already reasons well in one pass,
the extra recursion is mostly noise and latency.

Full methodology, significance tests, and the raw results:
[`experiments/EVALUATION.md`](experiments/EVALUATION.md).

---

## Project layout

```
impro/
├── core/        # recursive harness: spec, schedule, selection, ledger, library
├── cli/         # impro / skt commands + benchmark reproductions
├── buddy/       # ScienceBuddy experiment platform   (MIT)
├── mas/         # RecursiveMAS latent recursion      (MIT)
├── benchmarks/  # benchmark definitions
├── substrate/   # execution substrate
└── experiments/ # reproducible evaluations + results
```

Test, lint, verify:

```bash
pytest                          # full suite
ruff check impro tests scripts  # lint
python scripts/check_provenance.py   # verify vendored third_party checksums
```

---

## Licensing & attribution

Three upstream licenses are preserved in full:

| License | Covers | Text |
|---|---|---|
| **Apache-2.0** — Google Harness 2 | core runtime | [`LICENSE`](LICENSE) |
| **MIT** — ScienceBuddy | `impro/buddy` | [`impro/buddy/LICENSE`](impro/buddy/LICENSE) |
| **MIT** — RecursiveMAS | `impro/mas` | [`impro/mas/LICENSE`](impro/mas/LICENSE) |

SKT is a redesign whose design is inspired by all three. What was taken from
each, and why, is written up in [`NOTICE`](NOTICE) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Vendored dependencies under
`third_party/` are checksum-pinned and verified by `scripts/check_provenance.py`.
