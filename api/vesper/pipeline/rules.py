"""The eight rules (§6.5). Pure code: no database, no network, no model.

All eight always run and return a verdict, even after a refusal, so the UI shows the full picture.
Restrictions apply only to SEND_INVOICE; the other actions receive `allow`.
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from babel.numbers import format_currency
from pydantic import BaseModel

from vesper.models import Hint
from vesper.pipeline import messaging
from vesper.pipeline.schemas import Proposal

VerdictKind = Literal["allow", "defer", "approve", "refuse"]

RULES: list[tuple[str, str, str]] = [
    (
        "R1",
        "Hard failures are not chased",
        "If PayPal reports a hard failure, such as a refused transaction, a payer who cannot pay, "
        "or a denied capture, Vesper does not contact the customer. The case is held with a note for you.",
    ),
    (
        "R2",
        "Pending payments only wait",
        "If PayPal says the payment is still pending, no invoice is sent. The case waits for the payment to clear.",
    ),
    (
        "R3",
        "Consent required",
        "Vesper never emails a customer who has not agreed to email or who has opted out.",
    ),
    (
        "R4",
        "Contact window",
        "Messages go out only between 09:00 and 20:00 in the customer's own time zone. "
        "Outside those hours the invoice is queued for 09:00, not cancelled.",
    ),
    (
        "R5",
        "Frequency cap",
        "At most two messages per case and three per customer in any 30 days.",
    ),
    (
        "R6",
        "Freeze",
        "If the order was paid another way, refunded, or has an open dispute, the case closes and nothing is sent.",
    ),
    (
        "R7",
        "Approval threshold",
        "Amounts at or above your approval threshold wait for a person to approve them.",
    ),
    (
        "R8",
        "Message safety",
        "The model's message may use only approved placeholders, no digits, no links, and no promises "
        "like discounts or refunds. It must be under 400 characters and in the customer's language. "
        "If it fails, Vesper's standard template is used instead.",
    ),
]
RULE_NAMES = {rid: name for rid, name, _ in RULES}

FREEZE_REASONS = {"paid_elsewhere", "refunded"}
CASE_TOUCH_CAP = 2
CUSTOMER_TOUCH_CAP_30D = 3


class Verdict(BaseModel):
    rule_id: str
    name: str
    verdict: VerdictKind
    reason: str
    scheduled_for: datetime | None = None


class Final(BaseModel):
    outcome: VerdictKind
    scheduled_for: datetime | None = None
    refused_by: str | None = None
    use_fallback: bool = False


@dataclass(frozen=True)
class RuleInput:
    """Everything the rules look at, copied from the case and customer rows."""

    hint: Hint
    amount: Decimal
    currency: str
    frozen: bool
    closed_reason: str | None
    first_name: str
    place: str
    timezone: str
    locale: str
    email_consent: bool
    opted_out: bool
    touches_this_case: int
    touches_30d: int


@dataclass(frozen=True)
class Policy:
    approval_threshold: Decimal
    window_start: time
    window_end: time


def _v(rule_id: str, verdict: VerdictKind, reason: str, scheduled_for: datetime | None = None) -> Verdict:
    return Verdict(rule_id=rule_id, name=RULE_NAMES[rule_id], verdict=verdict, reason=reason, scheduled_for=scheduled_for)


def _money(amount: Decimal, currency: str) -> str:
    return format_currency(amount, currency, locale="en_US")


def next_window_open(now: datetime, tz: str, policy: Policy) -> datetime | None:
    """None when `now` is inside the window; otherwise the next window start, in UTC."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    if policy.window_start <= local.time() < policy.window_end:
        return None
    day = local.date() if local.time() < policy.window_start else local.date() + timedelta(days=1)
    return datetime.combine(day, policy.window_start, tzinfo=zone).astimezone(now.tzinfo)


def evaluate(
    inp: RuleInput, proposal: Proposal, now: datetime, policy: Policy
) -> tuple[list[Verdict], Final]:
    sends = proposal.action == "SEND_INVOICE"
    na = "Nothing will be sent, so this does not apply."
    out: list[Verdict] = []
    use_fallback = False

    # R1 reads the code-computed hint, never the model's category.
    if not sends:
        out.append(_v("R1", "allow", na))
    elif inp.hint == Hint.hard:
        out.append(_v("R1", "refuse", "PayPal reported a hard failure, so the customer is not contacted."))
    else:
        out.append(_v("R1", "allow", "This was not a hard failure."))

    if not sends:
        out.append(_v("R2", "allow", na))
    elif inp.hint == Hint.pending:
        out.append(_v("R2", "refuse", "The payment is still pending; Vesper waits for it to clear."))
    else:
        out.append(_v("R2", "allow", "Not pending."))

    if not sends:
        out.append(_v("R3", "allow", na))
    elif inp.opted_out:
        out.append(_v("R3", "refuse", f"{inp.first_name} has opted out of email."))
    elif not inp.email_consent:
        out.append(_v("R3", "refuse", f"{inp.first_name} has not agreed to email."))
    else:
        out.append(_v("R3", "allow", f"{inp.first_name} has agreed to email."))

    local_now = now.astimezone(ZoneInfo(inp.timezone)).strftime("%H:%M")
    if not sends:
        out.append(_v("R4", "allow", na))
    else:
        opens = next_window_open(now, inp.timezone, policy)
        if opens is None:
            out.append(_v("R4", "allow", f"It is {local_now} in {inp.place}."))
        else:
            start = policy.window_start.strftime("%H:%M")
            out.append(_v("R4", "defer", f"It is {local_now} in {inp.place}. Queued for {start}.", opens))

    if not sends:
        out.append(_v("R5", "allow", na))
    elif inp.touches_this_case >= CASE_TOUCH_CAP:
        out.append(_v("R5", "refuse", f"Already {inp.touches_this_case} messages for this case."))
    elif inp.touches_30d >= CUSTOMER_TOUCH_CAP_30D:
        out.append(_v("R5", "refuse", f"{inp.first_name} has had {inp.touches_30d} messages in the last 30 days."))
    elif inp.touches_this_case == 0:
        out.append(_v("R5", "allow", "First message for this case."))
    else:
        out.append(_v("R5", "allow", "Second message for this case; within the cap."))

    if not sends:
        out.append(_v("R6", "allow", na))
    elif inp.frozen:
        out.append(_v("R6", "refuse", "There is an open dispute on this payment."))
    elif inp.closed_reason == "paid_elsewhere":
        out.append(_v("R6", "refuse", "The order was paid another way."))
    elif inp.closed_reason == "refunded":
        out.append(_v("R6", "refuse", "The order was refunded."))
    else:
        out.append(_v("R6", "allow", "No dispute or refund."))

    threshold = _money(policy.approval_threshold, inp.currency)
    if not sends:
        out.append(_v("R7", "allow", na))
    elif inp.amount >= policy.approval_threshold:
        out.append(
            _v("R7", "approve", f"{_money(inp.amount, inp.currency)} is at or above your {threshold} threshold.")
        )
    else:
        out.append(_v("R7", "allow", f"Below {threshold}."))

    if not sends:
        out.append(_v("R8", "allow", "No message to check."))
    else:
        template = proposal.message_template or ""
        check = messaging.validate(template, inp.locale) if template else messaging.Validation(False, ["Empty."])
        if check.ok:
            out.append(_v("R8", "allow", "Passed."))
        else:
            use_fallback = True
            out.append(_v("R8", "allow", "Model message replaced by the standard template."))

    return out, _final(out, use_fallback)


def _final(verdicts: list[Verdict], use_fallback: bool) -> Final:
    refused = [v for v in verdicts if v.verdict == "refuse"]
    if refused:
        return Final(outcome="refuse", refused_by=refused[0].rule_id, use_fallback=use_fallback)
    if any(v.verdict == "approve" for v in verdicts):
        return Final(outcome="approve", use_fallback=use_fallback)
    deferred = [v.scheduled_for for v in verdicts if v.verdict == "defer" and v.scheduled_for]
    if deferred:
        return Final(outcome="defer", scheduled_for=min(deferred), use_fallback=use_fallback)
    return Final(outcome="allow", use_fallback=use_fallback)
