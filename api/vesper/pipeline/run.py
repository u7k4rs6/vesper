"""One case through the loop: Failed → Diagnosed → Proposed → Checked → (sent | scheduled | approval | held …).

Runs after the webhook or capture response has gone out. Commits after each stage so the Floor sees progress.
"""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vesper import sending
from vesper.cases import add_event, close_case
from vesper.config import get_settings
from vesper.models import Case, Customer, Hint, Stage, Touch
from vesper.pipeline import messaging
from vesper.pipeline._stage import StageFailed
from vesper.pipeline.diagnose import diagnose
from vesper.pipeline.evidence import build_packet
from vesper.pipeline.propose import propose
from vesper.pipeline.rules import RULE_NAMES, Final, Policy, RuleInput, Verdict, evaluate
from vesper.pipeline.schemas import Proposal

log = structlog.get_logger()

ACTION_WORDS = {
    "SEND_INVOICE": "send an invoice",
    "WAIT": "wait",
    "ESCALATE": "hand to a human",
    "NONE": "do nothing",
}


def policy() -> Policy:
    s = get_settings()
    return Policy(
        approval_threshold=s.approval_threshold,
        window_start=time.fromisoformat(s.contact_window_start),
        window_end=time.fromisoformat(s.contact_window_end),
    )


def place(customer: Customer) -> str:
    return customer.city or customer.country_code


def touch_counts(session: Session, case: Case, now: datetime) -> tuple[int, int]:
    this_case = session.scalar(select(func.count()).select_from(Touch).where(Touch.case_id == case.id)) or 0
    last_30d = session.scalar(
        select(func.count()).select_from(Touch).where(
            Touch.customer_id == case.customer_id, Touch.sent_at >= now - timedelta(days=30)
        )
    ) or 0
    return this_case, last_30d


def rule_input(session: Session, case: Case, now: datetime) -> RuleInput:
    c = case.customer
    this_case, last_30d = touch_counts(session, case, now)
    return RuleInput(
        hint=case.failure_category_hint,
        amount=case.amount,
        currency=case.currency,
        frozen=case.frozen,
        closed_reason=case.closed_reason,
        first_name=c.first_name,
        place=place(c),
        timezone=c.timezone,
        locale=c.locale,
        email_consent=c.email_consent,
        opted_out=c.opted_out,
        touches_this_case=this_case,
        touches_30d=last_30d,
    )


def _escalate(session: Session, case: Case, reason: str) -> None:
    case.stage = Stage.escalated
    add_event(session, case, "escalated", reason)


def _prepare_message(case: Case, proposal: Proposal, final: Final, now: datetime) -> dict:
    customer = case.customer
    if final.use_fallback or not proposal.message_template:
        template, language = messaging.fallback(customer.locale)
    else:
        template, language = proposal.message_template, proposal.language
    due = messaging.due_date(now.astimezone(ZoneInfo(customer.timezone)).date())
    rendered = messaging.render(
        template,
        first_name=customer.first_name,
        merchant=get_settings().merchant_name,
        description=case.description,
        amount=case.amount,
        currency=case.currency,
        locale=customer.locale,
        due=due,
    )
    return {
        "template": template,
        "rendered": rendered,
        "language": language,
        "fallback_used": final.use_fallback,
        "due_date": due.isoformat(),
        "scheduled_for": final.scheduled_for.isoformat() if final.scheduled_for else None,
        "sent_at": None,
        "payer_link": None,
    }


def _store_verdicts(case: Case, verdicts: list[Verdict], final: Final) -> None:
    case.verdicts = {
        "verdicts": [v.model_dump(mode="json") for v in verdicts],
        "final": final.model_dump(mode="json"),
    }


def run_case(session: Session, case_id: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    case = session.get(Case, case_id)
    if case is None or case.stage != Stage.failed:
        return
    log.info("pipeline_start", case_id=case.id)
    this_case, last_30d = touch_counts(session, case, now)
    packet = build_packet(
        case, case.customer, touches_case=this_case, touches_30d=last_30d,
        merchant=get_settings().merchant_name, now=now,
    )

    try:
        diagnosis = diagnose(packet)
    except StageFailed as e:
        _escalate(session, case, e.reason)
        session.commit()
        return
    case.diagnosis = diagnosis.model_dump()
    case.stage = Stage.diagnosed
    add_event(session, case, "diagnosed", f"Diagnosed as a {diagnosis.category} failure.")
    session.commit()

    try:
        proposal = propose(packet, diagnosis)
    except StageFailed as e:
        _escalate(session, case, e.reason)
        session.commit()
        return
    case.proposal = proposal.model_dump()
    case.stage = Stage.proposed
    add_event(session, case, "proposed", f"Proposed: {ACTION_WORDS[proposal.action]}.")
    session.commit()

    verdicts, final = evaluate(rule_input(session, case, now), proposal, now, policy())
    _store_verdicts(case, verdicts, final)
    case.stage = Stage.checked
    if proposal.action == "SEND_INVOICE":
        case.message = _prepare_message(case, proposal, final, now)
    _apply_outcome(session, case, proposal, final, now)
    session.commit()


def _apply_outcome(session: Session, case: Case, proposal: Proposal, final: Final, now: datetime) -> None:
    if proposal.action == "WAIT":
        case.stage = Stage.waiting
        add_event(session, case, "checked", "Checked: waiting for the payment to clear.")
        return
    if proposal.action == "ESCALATE":
        _escalate(session, case, "Checked: handed to a human, as the model proposed.")
        return
    if proposal.action == "NONE":
        close_case(session, case, "no_action", "Checked: closed with no message, as the model proposed.")
        return

    if final.outcome == "refuse":
        name = RULE_NAMES[final.refused_by]
        if final.refused_by == "R6":
            close_case(session, case, case.closed_reason or "frozen", f"Checked: closed by {name}.")
        elif case.failure_category_hint == Hint.pending:
            case.stage = Stage.waiting
            add_event(session, case, "checked", f"Checked: waiting, because of {name}.")
        else:
            case.stage = Stage.held
            add_event(session, case, "held", f"Checked: held by {name}.")
    elif final.outcome == "approve":
        case.stage = Stage.awaiting_approval
        add_event(session, case, "approval_requested", "Checked: waiting for your approval.")
    elif final.outcome == "defer":
        case.stage = Stage.scheduled
        start = get_settings().contact_window_start
        add_event(session, case, "scheduled",
                  f"Checked: queued for {start} {place(case.customer)} time by Contact window.")
    else:
        add_event(session, case, "checked", "Checked: all eight rules allow it.")
        session.commit()
        sending.send_case(session, case, now)


def recheck_and_send(session: Session, case: Case, now: datetime) -> None:
    """Before a queued or approved send: re-run the rules and act on R4–R6 (the window may have moved)."""
    proposal = Proposal.model_validate(case.proposal)
    verdicts, final = evaluate(rule_input(session, case, now), proposal, now, policy())
    by_id = {v.rule_id: v for v in verdicts}
    for rid in ("R5", "R6"):
        if by_id[rid].verdict == "refuse":
            if rid == "R6":
                close_case(session, case, case.closed_reason or "frozen", f"Before sending: closed by {RULE_NAMES[rid]}.")
            else:
                case.stage = Stage.held
                add_event(session, case, "held", f"Before sending: held by {RULE_NAMES[rid]}.")
            return
    if by_id["R4"].verdict == "defer":
        case.stage = Stage.scheduled
        case.message = {**(case.message or {}), "scheduled_for": by_id["R4"].scheduled_for.isoformat()}
        add_event(session, case, "scheduled", f"Before sending: queued again by Contact window. {by_id['R4'].reason}")
        return
    sending.send_case(session, case, now)


def run_case_in_new_session(case_id: str) -> None:
    """Entry point for background tasks: own session, never raises."""
    from vesper.db import SessionLocal

    with SessionLocal() as session:
        try:
            run_case(session, case_id)
        except Exception:
            session.rollback()
            log.exception("pipeline_failed", case_id=case_id)
