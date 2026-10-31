from __future__ import annotations

import os
import time
from pathlib import Path

from impro.core import runmark


def _harness(root: Path) -> Path:
    harness = root / "harness"
    (harness / "scripts").mkdir(parents=True)
    (harness / "systemprompt.md").write_text("be careful\n", encoding="utf-8")
    (harness / "scripts" / "check.py").write_text("print('ok')\n", encoding="utf-8")
    return harness


def test_fingerprint_is_stable_and_content_addressed(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    first = runmark.fingerprint(harness)
    assert first == runmark.fingerprint(harness)
    assert first != runmark.fingerprint(None)
    assert runmark.fingerprint(None) == "base"
    (harness / "systemprompt.md").write_text("be very careful\n", encoding="utf-8")
    assert runmark.fingerprint(harness) != first


def test_byproducts_do_not_change_identity(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    before = runmark.fingerprint(harness)
    (harness / "__pycache__").mkdir()
    (harness / "__pycache__" / "x.pyc").write_bytes(b"cache")
    (harness / ".DS_Store").write_bytes(b"noise")
    assert runmark.fingerprint(harness) == before


def test_marker_roundtrip_and_harness_match(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    where = tmp_path / "rollout"
    assert not runmark.is_complete(where)
    assert "never finished" in runmark.why_not(where)

    runmark.mark_complete(where, run_id="agg1", harness_dir=harness, extra={"note": "ok"})
    mark = runmark.read_mark(where)
    assert mark is not None
    assert mark["run_id"] == "agg1"
    assert mark["note"] == "ok"
    assert runmark.is_complete(where, harness_dir=harness)
    assert runmark.is_complete(where, match_harness=False)

    (harness / "systemprompt.md").write_text("changed\n", encoding="utf-8")
    assert not runmark.is_complete(where, harness_dir=harness)
    assert "different configuration" in runmark.why_not(where, harness_dir=harness)


def test_marker_replacement_is_atomic_and_leaves_no_temp(tmp_path: Path) -> None:
    where = tmp_path / "rollout"
    for i in range(3):
        runmark.mark_complete(where, run_id=f"r{i}", harness_dir=None)
        time.sleep(0.01)
    assert runmark.read_mark(where)["run_id"] == "r2"
    leftovers = [p.name for p in where.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_fingerprint_ignores_the_marker_itself(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    before = runmark.fingerprint(harness)
    runmark.mark_complete(harness, run_id="x", harness_dir=harness)
    assert runmark.fingerprint(harness) == before
    assert os.path.basename(runmark.MARK) == ".adapt_complete"
