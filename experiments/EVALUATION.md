# Does harness orchestration improve accuracy?

**Short answer: no — not on this model/dataset. A plain single-shot call was
the best condition.**

## Setup

- Model: `deepseek-ai/DeepSeek-V4-Flash-0731` (Baseten Model API, OpenAI-compatible)
- Dataset: bundled MedQA (`impro/mas/inference/dataset/medqa.json`), 100 questions
- Design: **paired** — same 100 questions across all four conditions
- Scoring: exact option-letter match against the gold answer
- Significance: McNemar exact test vs. baseline
- Script: `experiments/medqa_ab.py`

## What each condition tests

| Condition | Technique | Idea being tested | Calls/q |
|---|---|---|---|
| A_baseline | one call | control (no harness) | 1 |
| B_refine | generate -> critique -> revise | RecursiveMAS recursive self-refinement | ~3 |
| C_vote | 5 samples -> majority vote | ScienceBuddy self-consistency | 5 |
| D_harness | 3 refined samples -> vote | both combined | ~14 |

## Results

| Condition | Accuracy | vs baseline | McNemar p | Cost/q |
|---|---|---|---|---|
| A_baseline | **94%** | — | — | $0.00012 |
| B_refine | 91% | -3 | 0.51 | $0.00064 |
| C_vote | 93% | -1 | 1.0 | $0.00139 |
| D_harness | 92% | -2 | 0.63 | $0.00290 |

- No harness condition beat baseline. All deltas were **negative** and
  **not significant** (p > 0.05).
- The one consistent pattern: **self-refinement broke more answers than it
  fixed** (B_refine: 6 baseline-correct answers broken vs. 3 fixed). This is a
  known failure mode of self-critique on already-strong models.
- The harness cost **3-8x more per question** (D_harness ~24x the calls) for no
  accuracy gain.

## Total spend

~$0.74 across three runs (two invalidated by bugs found and fixed during the
process; see below). The final valid run cost **$0.29**.

## Honest scope

This tests the **orchestration techniques** on a **strong** reasoning model.
It does **not** test `impro.mas`'s trained latent adapter weights, which need a
local GPU + HF checkpoints and cannot run over an HTTP chat API.

The upstream frameworks' headline gains come from *small base models* (e.g.
gemma-3-4b) where orchestration + training lift a weak model. Whether the
technique helps a *weak* base model is **untested here**. What this shows is
narrower: **stacking self-refinement / self-consistency on a strong single-call
model gave zero benefit and added cost.**

## Data-quality bugs found and fixed during the run

The first two runs were discarded after finding scoring bugs. Recorded here so
the result is auditable:

1. `majority()` crashed on unparseable samples (`None in "ABCD"` -> TypeError),
   zeroing out the multi-sample conditions. Fixed to skip `None`.
2. Reasoning-model truncation: `max_tokens=512` let the reasoning trace consume
   the budget, returning empty `content` -> false "no answer". Fixed with a
   `reasoning_content` fallback and `max_tokens=4096`.
3. Gold-answer matching was too strict and silently dropped 10 questions.
   Fixed with normalized + substring matching.
4. **Non-unique `idx`:** the dataset has 300 items but only 200 unique `idx`
   values (0-99 appear twice). Keying predictions/gold-map by `idx` collided
   duplicate questions and corrupted the gold map. Fixed by keying on the
   unique list position (`qid`).

Reproduce with:

```
BASETEN_API_KEY=... python experiments/medqa_ab.py --n 100 --seed 42 --concurrency 6
python experiments/medqa_ab.py --summarize
```
