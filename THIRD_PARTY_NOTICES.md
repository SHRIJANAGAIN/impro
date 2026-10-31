# SKT — Third-Party Notices

**SKT** is a redesign whose design is **inspired by** three open-source
tools. This file lists every third-party component in this distribution,
its license, where its license text lives in-tree, and what was ported from
it. Full attribution prose is in [`NOTICE`](NOTICE).

## 1. Frameworks SKT is built on (design-inspired, code ported in-tree)

| # | Tool | Upstream tree | License | License text in this repo | Ported as |
|---|------|---------------|---------|---------------------------|-----------|
| 1 | **Harness 2** (Google) | `harness2-main` | Apache License 2.0 | [`LICENSE`](LICENSE) | `impro/` core runtime (`core`, `cli`, `substrate`, `benchmarks`, `adapter`, `config`, `preflight`, `install`) |
| 2 | **ScienceBuddy** (XShuhan) | `ScienceBuddy-main` | MIT License | [`impro/buddy/LICENSE`](impro/buddy/LICENSE) | `impro.buddy` package + `impro buddy` CLI |
| 3 | **RecursiveMAS** | `RecursiveMAS-main` | MIT License | [`impro/mas/LICENSE`](impro/mas/LICENSE) | `impro.mas` package + `impro mas` CLI |

### Why each tool was used

- **Harness 2** — policy-first agent security ("policy-only" by default),
  lifecycle hooks around every tool call, deterministic multi-agent
  orchestration, token/rollout budgets, streaming tool-arg handling, and a
  mature CLI/session model. It is the core agent runtime of SKT. Its
  Apache-2.0 license, `Copyright 2026 Google LLC` source headers, and
  functional protocol keys (`harness`, `harness.py`) are preserved; only
  user-facing product text is branded as SKT.
- **ScienceBuddy** — reproducible benchmark runs (MMLU, GPQA, HellaSwag,
  Math500, ...), multi-backend serving (VLLM / SGLang / Megatron), Ray-based
  distributed training, and structured run configs with HTML reporting. It
  supplies SKT's ML experiment platform. MIT license and the `impro-buddy`
  package/CLI name are preserved.
- **RecursiveMAS** — recursive multi-turn reasoning with inner/outer agent
  loops, a GRPO trainer for multi-agent systems, and built-in MedQA
  evaluation with Hugging Face models. It supplies SKT's multi-agent
  reasoning and training system. MIT license preserved; upstream Hugging
  Face dataset/model IDs (`RecursiveMAS/...`, `google/gemma-3-4b-it`) are
  functional references and kept unchanged.

**Reason for combining them:** no single upstream provided a secure
coding-agent core, a reproducible multi-framework ML experiment platform,
and a recursive multi-agent reasoning/training system at once. SKT merges
the three under one package and one CLI (`skt`) with shared config, auth,
and sandbox, while keeping every upstream license and attribution intact.

## 2. Bundled third-party code

These components are vendored under `third_party/` and pinned by
`scripts/check_provenance.py`.

| Component | License | License text |
|-----------|---------|--------------|
| Zod | MIT | `third_party/zod/LICENSE` |
| jsonrepair | MIT | `third_party/jsonrepair/LICENSE` |
| PyYAML | MIT | `third_party/pyyaml/LICENSE` |
| python-dotenv | BSD-3-Clause | `third_party/python-dotenv/LICENSE` |
| cli-table3 | MIT | `third_party/cli-table3/LICENSE` |
| Inquirer.js | MIT | `third_party/inquirer/LICENSE` |
| tmuxp (portions of the tmux integration) | ISC | `third_party/tmuxp/LICENSE` |

## 3. Models and datasets (referenced, not bundled)

| Item | Upstream | Used by |
|------|----------|---------|
| `RecursiveMAS/R1_0528_filtered` (dataset, based on `deepseek-ai/DeepSeek-R1-0528`, MIT) | Hugging Face Hub | `impro/mas` inference + train |
| `RecursiveMAS/math_dataset` (dataset) | Hugging Face Hub | `impro/mas` train |
| `openbmb/M-A-P-Open-Reasoning-Corpus-Math` (dataset) | Hugging Face Hub | `impro/mas` train |
| `google/genesis-docstring-python` (dataset) | Hugging Face Hub | `impro/mas` train |
| `RecursiveMAS/gemma-3-4b-it-unsloth-bnb-4bit` (model, based on `google/gemma-3-4b-it`, Google DeepMind) | Hugging Face Hub | `impro/mas` inference + train |
| `RecursiveMAS/gemma-3-12b-it-unsloth-bnb-4bit` (model, based on `gemma-3-12b-it`, Google DeepMind) | Hugging Face Hub | `impro/mas` train |

Model weights are **not** included in this source distribution. Download
them with the Hugging Face CLI after accepting the model license.
