"""POST /api/demo/fail — the judge's button (§7). Demo mode only; rate-limited (04_SECURITY.md §9)."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from vesper.auth import require_dashboard_token
from vesper.cases import create_case
from vesper.config import get_settings
from vesper.db import get_session
from vesper.demo_customers import next_demo_customer
from vesper.limits import global_key, limiter
from vesper.models import Source
from vesper.paypal.client import PayPalError, get_client
from vesper.pipeline.run import run_case_in_new_session

router = APIRouter(prefix="/api/demo", dependencies=[Depends(require_dashboard_token)])

EVENT_TYPES = {"subscription": "BILLING.SUBSCRIPTION.PAYMENT.FAILED", "capture_denied": "PAYMENT.CAPTURE.DENIED"}
# Payments v2 shapes the capture as `amount.value`; without this PayPal sends the older v1 sample.
RESOURCE_VERSIONS = {"capture_denied": "2.0"}


class FailRequest(BaseModel):
    kind: Literal["subscription", "capture_denied"]


@router.post("/fail")
@limiter.limit("6/minute")
@limiter.limit("60/hour", key_func=global_key)
def fail_a_payment(
    request: Request, body: FailRequest, background: BackgroundTasks, session: Session = Depends(get_session)
):
    settings = get_settings()
    if settings.demo_fail_strategy == "internal":
        # Fallback when simulated events cannot be verified: create the case directly, labelled "Seeded for demo".
        sub = body.kind == "subscription"
        case = create_case(
            session,
            source=Source.seeded,
            customer=next_demo_customer(session),
            amount=settings.demo_subscription_amount if sub else Decimal("89.00"),
            currency="USD",
            description="Monthly plan" if sub else "Linen Throw",
            failure_code="SUBSCRIPTION_PAYMENT_FAILED" if sub else "DENIED",
        )
        session.commit()
        background.add_task(run_case_in_new_session, case.id)
        return {"ok": True, "strategy": "internal", "case_id": case.id}

    try:
        get_client().request(
            "POST",
            "/v1/notifications/simulate-event",
            json={
                "webhook_id": settings.paypal_webhook_id,
                "event_type": EVENT_TYPES[body.kind],
                **({"resource_version": RESOURCE_VERSIONS[body.kind]} if body.kind in RESOURCE_VERSIONS else {}),
            },
        )
    except PayPalError:
        return JSONResponse(
            status_code=502, content={"error": {"code": "paypal_error", "message": "PayPal could not send the event."}}
        )
    # The case arrives through the webhook listener, verified like any other event.
    return {"ok": True, "strategy": "simulate_event"}
