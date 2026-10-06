"""Webhook verification and dispatch (§5.4, 04_SECURITY.md §7). No handler runs before verification."""

import json
from dataclasses import dataclass, field
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from vesper.cases import add_event, close_case, create_case, open_case_for_order, resolve_customer
from vesper.config import get_settings
from vesper.demo_customers import next_demo_customer
from vesper.models import TERMINAL_STAGES, Case, ProcessedWebhook, Source, Stage, utcnow
from vesper.paypal import orders
from vesper.paypal.client import PayPalClient, PayPalError

log = structlog.get_logger()

TRANSMISSION_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}

EVENT_TYPES = [
    "PAYMENT.CAPTURE.DENIED",
    "PAYMENT.CAPTURE.PENDING",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.REFUNDED",
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED",
    "INVOICING.INVOICE.PAID",
    "INVOICING.INVOICE.CANCELLED",
    "CUSTOMER.DISPUTE.CREATED",
]


class VerificationUnavailable(Exception):
    """PayPal's verification endpoint could not be reached; respond 503 so PayPal retries."""


def verify(client: PayPalClient, headers: dict[str, str], raw_body: bytes) -> bool:
    lowered = {k.lower(): v for k, v in headers.items()}
    fields = {name: lowered.get(header) for name, header in TRANSMISSION_HEADERS.items()}
    if not all(fields.values()):
        return False
    fields["webhook_id"] = get_settings().paypal_webhook_id
    # Splice the raw body in byte-for-byte; re-serialising it could change what PayPal signed.
    prefix = json.dumps(fields)[:-1].encode()
    payload = prefix + b', "webhook_event": ' + raw_body + b"}"
    try:
        body = client.request("POST", "/v1/notifications/verify-webhook-signature", content=payload)
    except PayPalError as e:
        if e.status >= 500:
            raise VerificationUnavailable from e
        return False
    except Exception as e:  # network, timeout, auth
        raise VerificationUnavailable from e
    return body.get("verification_status") == "SUCCESS"


@dataclass
class DispatchResult:
    duplicate: bool = False
    new_case_ids: list[str] = field(default_factory=list)


def handle(session: Session, client: PayPalClient, event: dict) -> DispatchResult:
    """Dedupe and dispatch inside one transaction. The caller commits."""
    event_id = event.get("id")
    if not event_id:
        return DispatchResult()
    try:
        with session.begin_nested():
            session.add(ProcessedWebhook(event_id=event_id))
            session.flush()
    except IntegrityError:
        return DispatchResult(duplicate=True)

    kind = event.get("event_type", "")
    resource = event.get("resource") or {}
    handler = _HANDLERS.get(kind)
    result = DispatchResult()
    if handler:
        handler(session, client, resource, result)
    log.info("webhook", event_id=event_id, event_type=kind, cases=result.new_case_ids)
    return result


def _amount(obj: dict | None) -> tuple[Decimal, str] | None:
    if not obj or "value" not in obj:
        return None
    return Decimal(obj["value"]), obj.get("currency_code", "USD")


def _order_id(capture: dict) -> str | None:
    return ((capture.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")


def _payer_for_order(session: Session, client: PayPalClient, order_id: str | None):
    """The payer from the order, or None when PayPal has no usable payer (simulated events)."""
    if order_id:
        try:
            email, name, country = orders._payer(orders.get_order(client, order_id))
            if email:
                return resolve_customer(session, email, name, country)
        except Exception:
            pass
    return None


def _capture_case(source: Source, failure_code: str):
    def handler(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
        money = _amount(res.get("amount"))
        order_id = _order_id(res)
        customer = _payer_for_order(session, client, order_id)
        description = "Order " + (order_id or res.get("id", ""))
        if customer is None:
            # A simulated event: PayPal's sample payer and amount are arbitrary, so use the demo store's product.
            customer = next_demo_customer(session)
            if get_settings().demo_mode:
                money, description = (Decimal("89.00"), "USD"), "Linen Throw"
        if money is None:
            log.warning("webhook_no_amount", event_type=source.value)
            return
        case = create_case(
            session,
            source=source,
            customer=customer,
            amount=money[0],
            currency=money[1],
            description=description,
            failure_code=failure_code,
            paypal_order_id=order_id,
            paypal_capture_id=res.get("id"),
        )
        add_event(session, case, "webhook", f"PayPal reported {failure_code} by webhook.")
        result.new_case_ids.append(case.id)

    return handler


def _close_for_order(reason: str, text: str):
    def handler(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
        order_id = _order_id(res)
        case = open_case_for_order(session, order_id) if order_id else None
        if case:
            close_case(session, case, reason, text)

    return handler


def _subscription_failed(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
    settings = get_settings()
    subscriber = res.get("subscriber") or {}
    email = subscriber.get("email_address")
    if email and not settings.demo_mode:
        name = " ".join(filter(None, [(subscriber.get("name") or {}).get(k) for k in ("given_name", "surname")]))
        country = ((subscriber.get("shipping_address") or {}).get("address") or {}).get("country_code")
        customer = resolve_customer(session, email, name or None, country)
        failed = (res.get("billing_info") or {}).get("last_failed_payment") or {}
        money = _amount(failed.get("amount"))
    else:
        # Simulated sample events carry no usable payer: attach a demo customer and the demo plan price.
        customer = next_demo_customer(session)
        money = None
    if money is None:
        money = (settings.demo_subscription_amount, "USD")
    case = create_case(
        session,
        source=Source.subscription_failed,
        customer=customer,
        amount=money[0],
        currency=money[1],
        description="Monthly plan",
        failure_code="SUBSCRIPTION_PAYMENT_FAILED",
        paypal_subscription_id=res.get("id"),
        event_text="Payment failed: subscription renewal did not go through.",
    )
    add_event(session, case, "webhook", "PayPal reported a failed subscription payment by webhook.")
    result.new_case_ids.append(case.id)


def _invoice_case(session: Session, res: dict) -> Case | None:
    invoice_id = res.get("id") or (res.get("invoice") or {}).get("id")
    if not invoice_id:
        return None
    return session.scalars(select(Case).where(Case.paypal_invoice_id == invoice_id)).first()


def _invoice_paid(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
    case = _invoice_case(session, res)
    if case and case.stage != Stage.recovered:
        case.stage = Stage.recovered
        case.recovered_at = utcnow()
        add_event(session, case, "recovered", "The customer paid the invoice. Recovered.")


def _invoice_cancelled(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
    case = _invoice_case(session, res)
    if case and case.stage not in TERMINAL_STAGES:
        close_case(session, case, "invoice_cancelled", "The invoice was cancelled. Closed.")


def _dispute_created(session: Session, client: PayPalClient, res: dict, result: DispatchResult) -> None:
    for tx in res.get("disputed_transactions") or []:
        capture_id = tx.get("seller_transaction_id")
        if not capture_id:
            continue
        for case in session.scalars(select(Case).where(Case.paypal_capture_id == capture_id)):
            case.frozen = True
            add_event(session, case, "webhook", "A dispute was opened on this payment. Frozen.")


_HANDLERS = {
    "PAYMENT.CAPTURE.DENIED": _capture_case(Source.capture_denied, "DENIED"),
    "PAYMENT.CAPTURE.PENDING": _capture_case(Source.capture_pending, "PENDING"),
    "PAYMENT.CAPTURE.COMPLETED": _close_for_order("paid_elsewhere", "The order was paid another way. Closed."),
    "PAYMENT.CAPTURE.REFUNDED": _close_for_order("refunded", "The order was refunded. Closed."),
    "BILLING.SUBSCRIPTION.PAYMENT.FAILED": _subscription_failed,
    "INVOICING.INVOICE.PAID": _invoice_paid,
    "INVOICING.INVOICE.CANCELLED": _invoice_cancelled,
    "CUSTOMER.DISPUTE.CREATED": _dispute_created,
}
