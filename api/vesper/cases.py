"""Creating cases and writing to the append-only timeline."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from vesper.models import TERMINAL_STAGES, Case, CaseEvent, Customer, Source, Stage, utcnow
from vesper.pipeline.taxonomy import hint_for
from vesper.tz_by_country import tz_and_locale


def add_event(session: Session, case: Case, kind: str, text: str, data: dict | None = None) -> CaseEvent:
    ev = CaseEvent(case_id=case.id, kind=kind, text=text, data=data)
    session.add(ev)
    return ev


def resolve_customer(session: Session, email: str, name: str | None, country: str | None) -> Customer:
    found = session.scalars(select(Customer).where(Customer.email == email).order_by(Customer.created_at)).first()
    if found:
        return found
    tz, locale = tz_and_locale(country)
    c = Customer(
        display_name=name or email.split("@")[0],
        email=email,
        country_code=(country or "US").upper(),
        timezone=tz,
        locale=locale,
        email_consent=True,
        opted_out=False,
    )
    session.add(c)
    session.flush()
    return c


def open_case_for_order(session: Session, order_id: str) -> Case | None:
    return session.scalars(
        select(Case)
        .where(Case.paypal_order_id == order_id, Case.stage.not_in(list(TERMINAL_STAGES)))
        .order_by(Case.created_at.desc())
    ).first()


def create_case(
    session: Session,
    *,
    source: Source,
    customer: Customer,
    amount: Decimal,
    currency: str,
    description: str,
    failure_code: str,
    paypal_order_id: str | None = None,
    paypal_capture_id: str | None = None,
    paypal_subscription_id: str | None = None,
    event_text: str | None = None,
) -> Case:
    """Idempotent per order: an open case for the same order is returned instead of a duplicate."""
    if paypal_order_id:
        existing = open_case_for_order(session, paypal_order_id)
        if existing:
            return existing
    case = Case(
        source=source,
        customer=customer,
        customer_id=customer.id,
        amount=amount,
        currency=currency,
        description=description,
        failure_code=failure_code,
        failure_category_hint=hint_for(failure_code),
        paypal_order_id=paypal_order_id,
        paypal_capture_id=paypal_capture_id,
        paypal_subscription_id=paypal_subscription_id,
        stage=Stage.failed,
    )
    session.add(case)
    session.flush()
    ref = f" on order {paypal_order_id}" if paypal_order_id else ""
    add_event(session, case, "created", event_text or f"Payment failed: {failure_code}{ref}.")
    return case


def close_case(session: Session, case: Case, reason: str, text: str) -> None:
    case.stage = Stage.closed
    case.closed_reason = reason
    case.closed_at = utcnow()
    add_event(session, case, "closed", text)
