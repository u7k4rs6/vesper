"""Demo store (§7). Exists only in demo mode. The only router that imports paypal.orders."""

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from vesper.cases import add_event, create_case, resolve_customer
from vesper.db import get_session
from vesper.limits import limiter
from vesper.models import Source
from vesper.paypal import orders
from vesper.paypal.client import PayPalError, get_client
from vesper.pipeline.run import run_case_in_new_session

PRODUCT = {"name": "Linen Throw", "amount": Decimal("89.00"), "currency": "USD"}

router = APIRouter(prefix="/api/demo/store")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.post("/orders")
@limiter.limit("20/minute")
def create_store_order(request: Request):
    try:
        order_id = orders.create_order(get_client(), PRODUCT["amount"], PRODUCT["currency"], PRODUCT["name"])
    except PayPalError:
        return _error(502, "paypal_error", "PayPal could not create the order.")
    return {"order_id": order_id}


@router.post("/orders/{order_id}/capture")
@limiter.limit("20/minute")
def capture_store_order(
    request: Request,
    background: BackgroundTasks,
    order_id: str,
    force_decline: bool = False,
    session: Session = Depends(get_session),
):
    client = get_client()
    outcome = orders.capture_order(client, order_id, force_decline)
    if outcome.status == "completed":
        return {"status": "completed"}
    if outcome.status == "error":
        return _error(502, "capture_failed", "The payment could not be completed.")

    email, name, country = outcome.payer_email, outcome.payer_name, outcome.payer_country
    if not email:
        # A declined capture returns no payer; the approved order still has one.
        try:
            email, name, country = orders._payer(orders.get_order(client, order_id))
        except PayPalError:
            email = None
    if not email:
        return _error(502, "no_payer", "PayPal did not return the payer for this order.")

    customer = resolve_customer(session, email, name, country)
    source = Source.capture_pending if outcome.status == "pending" else Source.checkout_decline
    case = create_case(
        session,
        source=source,
        customer=customer,
        amount=PRODUCT["amount"],
        currency=PRODUCT["currency"],
        description=PRODUCT["name"],
        failure_code=outcome.failure_code or "UNKNOWN",
        paypal_order_id=order_id,
        paypal_capture_id=outcome.capture_id,
    )
    if force_decline:
        add_event(session, case, "webhook", "Forced with PayPal's sandbox negative-testing header.")
    session.commit()
    background.add_task(run_case_in_new_session, case.id)
    return {"status": "failed", "case_id": case.id}
