#!/usr/bin/env python3
"""Paired A/B test: does harness-style orchestration improve accuracy?

Same model (deepseek-ai/DeepSeek-V4-Flash-0731), same MedQA questions, four
conditions compared pairwise per-question:

  A. baseline  -- one single-shot call (no harness).
  B. refine    -- recursive self-refinement (RecursiveMAS idea): generate,
                  then critique + revise. 2 calls.
  C. vote      -- self-consistency majority vote (ScienceBuddy idea): k
                  independent samples, majority. k calls.
  D. harness   -- both techniques combined: k=3 refined samples, majority
                  vote. 3*2 calls + aggregation.

This tests the *orchestration techniques*, NOT impro.mas's trained latent
adapter weights (which need a local GPU + HF checkpoints and cannot run over
an HTTP API). Reported honestly as such.

Cost is tracked from the API usage fields and printed. Results checkpoint to
JSON so the run is resumable and auditable.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
ENDPOINT = "https://inference.baseten.co/v1/chat/completions"
DATASET = Path("impro/mas/inference/dataset/medqa.json")
OUTDIR = Path("experiments/results")
PRICING = {  # USD per 1M tokens, from the user's Baseten plan
    "input": 0.13,
    "cached": 0.028,
    "output": 0.26,
}

# Answer letter -> we score by matching the option text to the gold answer.
LETTER_RE = re.compile(r"\b([ABCD])\b")


def _norm(s: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for robust matching."""
    s = str(s).lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_dataset(n: int, seed: int) -> list[dict]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rng = random.Random(seed)
    idx = list(range(len(data)))
    rng.shuffle(idx)
    idx = sorted(idx[:n])
    out = []
    dropped = 0
    for i in idx:
        item = data[i]
        ans_norm = _norm(item["answer"])
        gold = None
        for opt in item["options"]:
            letter, _, text = opt.partition(".")
            if _norm(text) == ans_norm:
                gold = letter.strip()
                break
        if gold is None:
            # substring fallback (handles minor wording drift)
            for opt in item["options"]:
                letter, _, text = opt.partition(".")
                ot = _norm(text)
                if ot and (ot in ans_norm or ans_norm in ot):
                    gold = letter.strip()
                    break
        if gold is None:
            m = re.match(r"\s*([ABCD])\b", str(item["answer"]))
            gold = m.group(1) if m else None
        if gold is None:
            dropped += 1
            continue
        # keep the FULL question (all choice text is inside the stem already).
        # qid = unique list position; idx is NOT unique in this dataset
        # (idx 0-99 each appear twice), so qid is the only safe dict key.
        out.append(
            {
                "qid": i,
                "idx": item["idx"],
                "question": item["question"].strip(),
                "options": item["options"],
                "gold": gold,
            }
        )
    if dropped:
        print(f"  (dropped {dropped} questions with unmatchable gold answer)")
    return out


class Meter:
    """Thread-safe token/cost accounting."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.in_tok = 0
        self.out_tok = 0
        self.cached_tok = 0
        self.calls = 0
        self.cost = 0.0

    def add(self, usage: dict) -> None:
        with self.lock:
            it = usage.get("prompt_tokens", 0) or 0
            ot = usage.get("completion_tokens", 0) or 0
            ct = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
            self.in_tok += it
            self.out_tok += ot
            self.cached_tok += ct
            self.calls += 1
            # cached tokens billed at the cached rate; the rest at input rate
            billable_in = max(it - ct, 0)
            self.cost += (
                billable_in * PRICING["input"]
                + ct * PRICING["cached"]
                + ot * PRICING["output"]
            ) / 1e6

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "calls": self.calls,
                "in_tok": self.in_tok,
                "out_tok": self.out_tok,
                "cached_tok": self.cached_tok,
                "cost_usd": round(self.cost, 6),
            }


class Client:
    def __init__(self, api_key: str, meter: Meter, max_retries: int = 5) -> None:
        self.key = api_key
        self.meter = meter
        self.max_retries = max_retries

    def chat(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        body = json.dumps(
            {
                "model": MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode()
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                ENDPOINT,
                data=body,
                headers={
                    "Authorization": "Bearer " + self.key,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    d = json.loads(r.read())
                if d.get("usage"):
                    self.meter.add(d["usage"])
                msg = d["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                if content:
                    return content
                # Reasoning model: if content was empty/truncated, the final
                # answer is often the last line of the reasoning trace.
                return (msg.get("reasoning_content") or "").strip()
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise
        return ""


def fmt_question(item: dict) -> str:
    opts = "\n".join(item["options"])
    return f"{item['question']}\n\n{opts}"


def extract_letter(text: str, item: dict | None = None) -> str | None:
    if not text:
        return None
    m = re.search(r"(?:answer|final|option)\s*[:\-]?\s*\*{0,2}([ABCD])\b", text, re.I)
    if m:
        return m.group(1)
    matches = LETTER_RE.findall(text)
    if matches:
        return matches[-1]
    # Fallback: model answered with option text instead of a letter.
    if item is not None:
        low = text.lower()
        for opt in item["options"]:
            letter, _, otext = opt.partition(".")
            otext = otext.strip().lower()
            if otext and otext in low:
                return letter.strip()
    return None


SYS = (
    "You are a careful medical exam taker. Read the question, reason briefly, "
    "then give the single best answer as a capital letter A, B, C, or D."
)


def cond_baseline(cli: Client, item: dict) -> str | None:
    r = cli.chat(
        [
            {"role": "system", "content": SYS},
            {"role": "user", "content": fmt_question(item) + "\n\nAnswer with just the letter."},
        ],
        temperature=0.0,
        max_tokens=4096,
    )
    return extract_letter(r, item)


def refine_once(cli: Client, item: dict, prev_letter: str | None) -> str | None:
    """Recursive self-refinement: critique the prior answer, then revise."""
    critique_msgs = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": fmt_question(item)},
        {
            "role": "assistant",
            "content": f"My answer was {prev_letter}.",
        },
        {
            "role": "user",
            "content": (
                "Critique that answer. Re-examine each option, catch any error, "
                "then give a revised single letter A/B/C/D on the final line."
            ),
        },
    ]
    r = cli.chat(critique_msgs, temperature=0.6, max_tokens=4096)
    return extract_letter(r, item)


def cond_refine(cli: Client, item: dict) -> str | None:
    first = cond_baseline(cli, item)
    if first is None:
        return None
    return refine_once(cli, item, first) or first


def sample_once(cli: Client, item: dict) -> str | None:
    r = cli.chat(
        [
            {"role": "system", "content": SYS},
            {"role": "user", "content": fmt_question(item)},
        ],
        temperature=0.6,
        max_tokens=4096,
    )
    return extract_letter(r, item)


def majority(letters: list[str | None]) -> str | None:
    letters = [x for x in letters if isinstance(x, str) and x in ("A", "B", "C", "D")]
    if not letters:
        return None
    counts: dict[str, int] = {}
    for x in letters:
        counts[x] = counts.get(x, 0) + 1
    best = max(counts.values())
    # deterministic tie-break: lowest letter among the tied
    tied = sorted([k for k, v in counts.items() if v == best])
    return tied[0]


def cond_vote(cli: Client, item: dict, k: int = 5) -> str | None:
    return majority([sample_once(cli, item) for _ in range(k)])


def cond_harness(cli: Client, item: dict, k: int = 3) -> str | None:
    """Combine both: k refined samples, then majority vote."""
    letters = []
    for _ in range(k):
        first = cond_baseline(cli, item)
        refined = refine_once(cli, item, first) if first else None
        letters.append(refined or first)
    return majority(letters)


CONDS = {
    "A_baseline": cond_baseline,
    "B_refine": cond_refine,
    "C_vote": cond_vote,
    "D_harness": cond_harness,
}


def run(
    n: int, seed: int, concurrency: int, only: list[str] | None = None
) -> None:
    api_key = os.environ.get("BASETEN_API_KEY")
    if not api_key:
        sys.exit("Set BASETEN_API_KEY")
    items = load_dataset(n, seed)
    print(f"Loaded {len(items)} MedQA questions (n={n}, seed={seed})")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    meter = Meter()
    conds = {k: v for k, v in CONDS.items() if (only is None or k in only)}

    for name, fn in conds.items():
        outfile = OUTDIR / f"{name}_{MODEL.split('/')[-1]}_n{len(items)}_seed{seed}.json"
        done: dict[str, str | None] = {}
        if outfile.exists():
            prev = json.loads(outfile.read_text(encoding="utf-8"))
            done = prev.get("preds", {})
            print(f"[{name}] resuming, {len(done)} already done")

        todo = [it for it in items if str(it["qid"]) not in done]
        print(f"[{name}] {len(todo)} questions to run ({concurrency} workers)")
        lock = threading.Lock()
        t0 = time.time()

        def work(item: dict) -> tuple[str, str | None]:
            cli = Client(api_key, meter)
            try:
                return str(item["qid"]), fn(cli, item)
            except Exception as e:  # noqa: BLE001
                print(f"[{name}] idx={item['idx']} ERROR {type(e).__name__}: {e}")
                return str(item["qid"]), None

        with cf.ThreadPoolExecutor(max_workers=concurrency) as ex:
            for i, (k, v) in enumerate(ex.map(work, todo), 1):
                with lock:
                    done[k] = v
                if i % 20 == 0 or i == len(todo):
                    snap = meter.snapshot()
                    correct = sum(
                        1
                        for it in items
                        if done.get(str(it["qid"])) == it["gold"]
                    )
                    ran = sum(1 for it in items if str(it["qid"]) in done)
                    acc_so_far = correct / ran if ran else 0
                    el = time.time() - t0
                    print(
                        f"  [{name}] {i}/{len(todo)} acc={acc_so_far:.3f} "
                        f"calls={snap['calls']} cost=${snap['cost_usd']:.4f} "
                        f"({el:.0f}s)"
                    )
                    # checkpoint
                    outfile.write_text(
                        json.dumps(
                            {
                                "model": MODEL,
                                "cond": name,
                                "n": len(items),
                                "seed": seed,
                                "preds": done,
                                "meter": meter.snapshot(),
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

        # final write
        outfile.write_text(
            json.dumps(
                {
                    "model": MODEL,
                    "cond": name,
                    "n": len(items),
                    "seed": seed,
                    "preds": done,
                    "meter": meter.snapshot(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        correct = sum(1 for it in items if done.get(str(it["qid"])) == it["gold"])
        acc = correct / len(items)
        print(f"[{name}] DONE acc={acc:.4f} ({correct}/{len(items)})")

    print("\n=== TOTAL (all conditions) ===")
    print(json.dumps(meter.snapshot(), indent=2))


def summarize() -> None:
    files = sorted(OUTDIR.glob("*.json"))
    if not files:
        print("No result files found.")
        return
    # Rebuild the gold map from the SAME sample the run used (n/seed are
    # stored per-file), keyed by the unique qid — NOT by idx, which is not
    # unique in this dataset (idx 0-99 each appear twice).
    first = json.loads(files[0].read_text(encoding="utf-8"))
    n, seed = first.get("n", 100), first.get("seed", 42)
    items = load_dataset(n, seed)
    gmap = {str(it["qid"]): it["gold"] for it in items}
    rows = []
    per_cond_preds: dict[str, dict[str, str | None]] = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        preds = d["preds"]
        per_cond_preds[d["cond"]] = preds
        correct = sum(1 for k, v in preds.items() if gmap.get(k) == v)
        rows.append(
            {
                "cond": d["cond"],
                "n": len(preds),
                "correct": correct,
                "acc": round(correct / len(preds), 4) if preds else 0,
            }
        )
    print(json.dumps(rows, indent=2))

    # McNemar paired test between baseline and each other condition
    def mcnemar(b: dict, c: dict) -> dict:
        only_b = only_c = both = neither = 0
        for k in gmap:
            if k not in b or k not in c:
                continue
            gb = b.get(k) == gmap[k]
            gc = c.get(k) == gmap[k]
            if gb and gc:
                both += 1
            elif gb and not gc:
                only_b += 1
            elif gc and not gb:
                only_c += 1
            else:
                neither += 1
        n_disc = only_b + only_c
        # two-sided exact binomial p-value
        if n_disc == 0:
            p = 1.0
        else:
            from math import comb

            k = min(only_b, only_c)
            tail = sum(comb(n_disc, i) for i in range(0, k + 1))
            p = min(1.0, 2 * tail / (2**n_disc))
        return {
            "baseline_only_right": only_b,
            "cond_only_right": only_c,
            "both_right": both,
            "neither_right": neither,
            "n_discordant": n_disc,
            "mcnemar_p": round(p, 5),
        }

    base = per_cond_preds.get("A_baseline", {})
    print("\n=== Paired vs baseline (McNemar exact) ===")
    for name, preds in per_cond_preds.items():
        if name == "A_baseline":
            continue
        print(name, json.dumps(mcnemar(base, preds)))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--summarize", action="store_true")
    a = ap.parse_args()
    if a.summarize:
        summarize()
    else:
        only = [x for x in a.only.split(",") if x] or None
        run(a.n, a.seed, a.concurrency, only)
