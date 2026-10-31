from __future__ import annotations

import pytest

from impro.core.ledger import BudgetError, Ledger, expected_rollouts, expected_sessions


def _exact(k: int) -> Ledger:
    ledger = Ledger(mode="agg", task_id="example", k=k)
    for i in range(1, expected_rollouts(k) + 1):
        ledger.rollout(f"r{i}")
    for i in range(1, expected_sessions(k) + 1):
        ledger.session(f"s{i}", usd=0.5 * i, attempts=i)
    return ledger


@pytest.mark.parametrize("k", [1, 2, 3])
def test_the_budget_identity_is_four_k_rollouts_and_three_k_sessions(k: int) -> None:
    ledger = _exact(k)
    assert (ledger.R, ledger.P) == (4 * k, 3 * k)
    ledger.assert_identity()
    payload = ledger.to_dict()
    assert payload["expected_R"] == 4 * k
    assert payload["expected_P"] == 3 * k
    assert payload["session_attempts"] == sum(range(1, 3 * k + 1))


def test_a_duplicate_label_is_named_before_the_counts_are_compared() -> None:
    ledger = _exact(2)
    ledger.rollout("r1")
    with pytest.raises(BudgetError) as caught:
        ledger.assert_identity()
    assert "DUPLICATE" in str(caught.value)
    assert "r1" in str(caught.value)


def test_a_missing_rollout_fails_with_the_labels_that_were_recorded() -> None:
    ledger = Ledger(mode="seq", task_id="example", k=1)
    for i in range(3):
        ledger.rollout(f"r{i}")
    for i in range(3):
        ledger.session(f"s{i}")
    with pytest.raises(BudgetError) as caught:
        ledger.assert_identity()
    assert "R=3 (want 4)" in str(caught.value)
    assert "r0, r1, r2" in str(caught.value)


def test_cost_splits_by_kind() -> None:
    ledger = Ledger(mode="agg", task_id="example", k=1)
    ledger.rollout("base1", usd=1.25)
    ledger.session("inv1", usd=2.5, attempts=2)
    assert ledger.rollout_usd == 1.25
    assert ledger.session_usd == 2.5
    assert ledger.usd == 3.75
    assert ledger.labels("rollout") == ["base1"]
