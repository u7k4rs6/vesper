"""The single path from a checked case to a PayPal invoice email.

`invoicing.send_invoice` is called from here and nowhere else (test_send_invoice_has_one_call_site).
"""

import time
from datetime import date, datetime

import httpx
import structlog
from sqlalchemy.orm import Session

from vesper.cases import add_event
from vesper.models import Case, Stage, Touch
from vesper.paypal import invoicing
from vesper.paypal.client import PayPalError, get_client

log = structlog.get_logger()

BACKOFF_S = (2, 8)  # three attempts over roughly ten to thirty seconds with network time


class _Unavailable(Exception):
    pass


def _with_backoff(fn):
    """Retry PayPal 5xx and network errors; the PayPal-Request-Id inside `fn` makes retries idempotent."""
    for attempt, delay in enumerate((*BACKOFF_S, None), start=1):
        try:
            return fn()
        except PayPalError as e:
            if e.status < 500:
                raise
        except httpx.TransportError:
            pass
        if delay is None:
            raise _Unavailable()
        log.warning("paypal_retry", attempt=attempt)
        time.sleep(delay)


def _queue_paused(session: Session, case: Case, now: datetime) -> None:
    case.stage = Stage.scheduled
    case.message = {**(case.message or {}), "scheduled_for": now.isoformat()}
    add_event(session, case, "scheduled", "Sending is paused by the kill switch. Queued until it is turned off.")


def send_case(session: Session, case: Case, now: datetime) -> None:
    message = case.message or {}
    client = get_client()
    try:
        if not case.paypal_invoice_id:
            due = date.fromisoformat(message["due_date"])
            case.paypal_invoice_id = _with_backoff(
                lambda: invoicing.create_invoice(client, case, message["rendered"], due=due)
            )
            session.flush()
        _with_backoff(lambda: invoicing.send_invoice(client, case.paypal_invoice_id, case_id=case.id))
    except invoicing.SendingPaused:
        _queue_paused(session, case, now)
        return
    except _Unavailable:
        case.stage = Stage.held
        add_event(session, case, "held", "PayPal was unavailable; try again from the case.")
        return
    except PayPalError as e:
        case.stage = Stage.held
        reason = next((i for i in e.issues if i), None) or e.body.get("name") or str(e.status)
        add_event(session, case, "held", f"PayPal refused the invoice ({reason}).", {"status": e.status, "issues": e.issues})
        return

    try:
        link = invoicing.payer_link(client, case.paypal_invoice_id)
    except (PayPalError, httpx.TransportError):
        link = None
    session.add(Touch(case_id=case.id, customer_id=case.customer_id, sent_at=now))
    case.stage = Stage.sent
    case.message = {**message, "sent_at": now.isoformat(), "payer_link": link}
    add_event(session, case, "sent", "Invoice sent. PayPal emailed it to the customer.")
