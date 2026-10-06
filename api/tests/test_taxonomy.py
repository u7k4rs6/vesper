from datetime import UTC, datetime

from vesper.models import Hint
from vesper.pipeline.rules import evaluate
from vesper.pipeline.taxonomy import hint_for
from tests.factories import POLICY, marta, send

NOON_MADRID = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def test_known_codes_map_to_hints():
    assert hint_for("INSTRUMENT_DECLINED") == Hint.soft
    assert hint_for("PAYER_ACTION_REQUIRED") == Hint.soft
    assert hint_for("SUBSCRIPTION_PAYMENT_FAILED") == Hint.soft
    assert hint_for("TRANSACTION_REFUSED") == Hint.hard
    assert hint_for("PAYER_CANNOT_PAY") == Hint.hard
    assert hint_for("DENIED") == Hint.hard
    assert hint_for("PENDING") == Hint.pending


def test_unrecognised_code_is_unknown():
    assert hint_for("SOMETHING_NEW") == Hint.unknown


def test_hallucinated_soft_cannot_unlock_hard_failure():
    # The model's diagnosis says "soft"; the rules never see it. They read the code-computed hint.
    hint = hint_for("TRANSACTION_REFUSED")
    verdicts, final = evaluate(marta(hint=hint), send(), NOON_MADRID, POLICY)
    assert verdicts[0].rule_id == "R1" and verdicts[0].verdict == "refuse"
    assert final.outcome == "refuse"
