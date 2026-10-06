"""Orders v2, for the demo store only. The only module allowed to call capture."""

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from vesper.paypal.client import PayPalClient, PayPalError

SOFT_ISSUES = {"INSTRUMENT_DECLINED", "PAYER_ACTION_REQUIRED"}
HARD_ISSUES = {"TRANSACTION_REFUSED", "PAYER_CANNOT_PAY"}


@dataclass
class CaptureOutcome:
    status: Literal["completed", "pending", "failed", "error"]
    failure_code: str | None = None
    capture_id: str | None = None
    payer_email: str | None = None
    payer_name: str | None = None
    payer_country: str | None = None


def create_order(client: PayPalClient, amount: Decimal, currency: str, description: str) -> str:
    body = client.request(
        "POST",
        "/v2/checkout/orders",
        json={
            "intent": "CAPTURE",
            "purchase_units": [
                {"description": description, "amount": {"currency_code": currency, "value": f"{amount:.2f}"}}
            ],
        },
    )
    return body["id"]


def get_order(client: PayPalClient, order_id: str) -> dict:
    return client.request("GET", f"/v2/checkout/orders/{order_id}")


def _payer(body: dict) -> tuple[str | None, str | None, str | None]:
    payer = body.get("payer") or {}
    name = payer.get("name") or {}
    full = " ".join(p for p in (name.get("given_name"), name.get("surname")) if p) or None
    country = (payer.get("address") or {}).get("country_code")
    return payer.get("email_address"), full, country


def capture_order(client: PayPalClient, order_id: str, force_decline: bool) -> CaptureOutcome:
    headers = {}
    if force_decline:
        headers["PayPal-Mock-Response"] = json.dumps({"mock_application_codes": "INSTRUMENT_DECLINED"})
    try:
        body = client.request(
            "POST",
            f"/v2/checkout/orders/{order_id}/capture",
            json={},
            request_id=f"order:{order_id}:capture",
            headers=headers,
        )
    except PayPalError as e:
        if e.status == 422:
            issue = next((i for i in e.issues if i in SOFT_ISSUES | HARD_ISSUES), None)
            if issue:
                return CaptureOutcome(status="failed", failure_code=issue)
        return CaptureOutcome(status="error")

    email, name, country = _payer(body)
    captures = [c for pu in body.get("purchase_units", []) for c in pu.get("payments", {}).get("captures", [])]
    capture = captures[0] if captures else {}
    cap_status = capture.get("status")
    common = dict(capture_id=capture.get("id"), payer_email=email, payer_name=name, payer_country=country)
    if cap_status == "PENDING":
        return CaptureOutcome(status="pending", failure_code="PENDING", **common)
    if cap_status in ("DECLINED", "FAILED"):
        return CaptureOutcome(status="failed", failure_code="DENIED", **common)
    if body.get("status") == "COMPLETED":
        return CaptureOutcome(status="completed", **common)
    return CaptureOutcome(status="error")
