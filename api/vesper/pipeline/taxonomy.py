"""PayPal failure code → category hint, computed before the model sees anything (§6.1).

Rules R1 and R2 read this hint, never the model's category.
"""

from vesper.models import Hint

HARD = frozenset({"TRANSACTION_REFUSED", "PAYER_CANNOT_PAY", "DENIED", "CAPTURE_DENIED"})
SOFT = frozenset({"INSTRUMENT_DECLINED", "PAYER_ACTION_REQUIRED", "SUBSCRIPTION_PAYMENT_FAILED"})
PENDING = frozenset({"PENDING"})


def hint_for(failure_code: str) -> Hint:
    code = failure_code.strip().upper()
    if code in HARD:
        return Hint.hard
    if code in SOFT:
        return Hint.soft
    if code in PENDING:
        return Hint.pending
    return Hint.unknown
