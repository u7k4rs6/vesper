from datetime import UTC, datetime
from decimal import Decimal

import pytest

from vesper.models import Hint
from vesper.pipeline.rules import RULES, evaluate
from vesper.pipeline.schemas import Proposal
from tests.factories import POLICY, marta, send

# 10:00 UTC = 12:00 in Madrid (CEST), inside the window.
MIDDAY = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
# 00:14 UTC = 02:14 in Madrid, outside the window.
NIGHT = datetime(2026, 10, 5, 0, 14, tzinfo=UTC)


def verdict(verdicts, rule_id):
    return next(v for v in verdicts if v.rule_id == rule_id)


def test_all_eight_rules_always_return_a_verdict_in_order():
    verdicts, _ = evaluate(marta(hint=Hint.hard, opted_out=True), send(), MIDDAY, POLICY)
    assert [v.rule_id for v in verdicts] == [rid for rid, _, _ in RULES] == [f"R{i}" for i in range(1, 9)]


def test_clean_case_is_allowed():
    verdicts, final = evaluate(marta(), send(), MIDDAY, POLICY)
    assert all(v.verdict == "allow" for v in verdicts)
    assert final.outcome == "allow" and not final.use_fallback


def test_r1_refuses_hard_failure():
    verdicts, final = evaluate(marta(hint=Hint.hard), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R1").verdict == "refuse"
    assert final.outcome == "refuse" and final.refused_by == "R1"


def test_r2_refuses_pending():
    verdicts, final = evaluate(marta(hint=Hint.pending), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R2").verdict == "refuse"
    assert final.refused_by == "R2"


@pytest.mark.parametrize("changes", [{"email_consent": False}, {"opted_out": True}])
def test_r3_refuses_without_consent(changes):
    verdicts, _ = evaluate(marta(**changes), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R3").verdict == "refuse"


def test_r4_defers_to_next_nine_local_in_madrid():
    verdicts, final = evaluate(marta(), send(), NIGHT, POLICY)
    r4 = verdict(verdicts, "R4")
    assert r4.verdict == "defer"
    assert r4.reason == "It is 02:14 in Madrid. Queued for 09:00."
    # 09:00 CEST on 5 October = 07:00 UTC.
    assert final.outcome == "defer"
    assert final.scheduled_for == datetime(2026, 10, 5, 7, 0, tzinfo=UTC)


def test_r4_after_window_defers_to_tomorrow():
    # 19:30 UTC = 21:30 in Madrid, after the window closes.
    evening = datetime(2026, 10, 5, 19, 30, tzinfo=UTC)
    _, final = evaluate(marta(), send(), evening, POLICY)
    assert final.scheduled_for == datetime(2026, 10, 6, 7, 0, tzinfo=UTC)


def test_r4_uses_customer_timezone_not_server():
    # 03:00 UTC is 11:00 in Singapore and 05:00 in Madrid.
    instant = datetime(2026, 10, 5, 3, 0, tzinfo=UTC)
    sg, _ = evaluate(marta(timezone="Asia/Singapore", place="Singapore"), send(), instant, POLICY)
    md, _ = evaluate(marta(), send(), instant, POLICY)
    assert verdict(sg, "R4").verdict == "allow"
    assert verdict(md, "R4").verdict == "defer"


def test_r4_window_end_is_exclusive():
    # 18:00 UTC = 20:00 Madrid.
    _, final = evaluate(marta(), send(), datetime(2026, 10, 5, 18, 0, tzinfo=UTC), POLICY)
    assert final.outcome == "defer"


@pytest.mark.parametrize("changes", [{"touches_this_case": 2}, {"touches_30d": 3}])
def test_r5_frequency_cap(changes):
    verdicts, _ = evaluate(marta(**changes), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R5").verdict == "refuse"


def test_r5_allows_second_touch():
    verdicts, _ = evaluate(marta(touches_this_case=1, touches_30d=2), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R5").verdict == "allow"


@pytest.mark.parametrize(
    "changes", [{"frozen": True}, {"closed_reason": "paid_elsewhere"}, {"closed_reason": "refunded"}]
)
def test_r6_freeze(changes):
    verdicts, final = evaluate(marta(**changes), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R6").verdict == "refuse"
    assert final.refused_by == "R6"


def test_r7_threshold_is_inclusive():
    verdicts, final = evaluate(marta(amount=Decimal("500.00")), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R7").verdict == "approve"
    assert verdict(verdicts, "R7").reason == "$500.00 is at or above your $500.00 threshold."
    assert final.outcome == "approve"


def test_r7_below_threshold():
    verdicts, _ = evaluate(marta(amount=Decimal("499.99")), send(), MIDDAY, POLICY)
    assert verdict(verdicts, "R7").reason == "Below $500.00."


def test_r8_bad_template_uses_fallback_and_still_allows():
    verdicts, final = evaluate(marta(), send("Hola {first_name}, 20% de descuento"), MIDDAY, POLICY)
    assert verdict(verdicts, "R8").verdict == "allow"
    assert verdict(verdicts, "R8").reason == "Model message replaced by the standard template."
    assert final.use_fallback and final.outcome == "allow"


def test_r8_missing_template_uses_fallback():
    _, final = evaluate(marta(), send(template=None), MIDDAY, POLICY)
    assert final.use_fallback


@pytest.mark.parametrize("action", ["WAIT", "ESCALATE", "NONE"])
def test_non_send_actions_are_always_allowed(action):
    proposal = Proposal(action=action, rationale="x", language="es")
    verdicts, final = evaluate(marta(hint=Hint.hard, opted_out=True, frozen=True), proposal, NIGHT, POLICY)
    assert all(v.verdict == "allow" for v in verdicts)
    assert final.outcome == "allow" and not final.use_fallback


def test_precedence_refuse_beats_approve_beats_defer():
    big = marta(amount=Decimal("900"))
    _, final = evaluate(big, send(), NIGHT, POLICY)
    assert final.outcome == "approve"
    _, final = evaluate(marta(amount=Decimal("900"), opted_out=True), send(), NIGHT, POLICY)
    assert final.outcome == "refuse"
    _, final = evaluate(marta(), send(), NIGHT, POLICY)
    assert final.outcome == "defer"


def test_first_refusing_rule_is_reported():
    _, final = evaluate(marta(hint=Hint.hard, opted_out=True), send(), MIDDAY, POLICY)
    assert final.refused_by == "R1"
