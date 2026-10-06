"""PayPal Invoicing v2: the only customer-facing channel (§5.3).

The invoice amount is read from the case row inside `create_invoice`. No function here takes an amount.
"""

from datetime import date

from vesper.config import get_settings
from vesper.models import Case
from vesper.paypal.client import PayPalClient


class SendingPaused(Exception):
    """The kill switch is on. Raised before any request leaves."""


def create_invoice(client: PayPalClient, case: Case, note: str, *, due: date) -> str:
    settings = get_settings()
    number = client.request(
        "POST", "/v2/invoicing/generate-next-invoice-number", request_id=f"case:{case.id}:invoice:number"
    )["invoice_number"]
    body = client.request(
        "POST",
        "/v2/invoicing/invoices",
        request_id=f"case:{case.id}:invoice:create",
        headers={"Prefer": "return=representation"},
        json={
            "detail": {
                "currency_code": case.currency,
                "invoice_number": number,
                "note": note,
                "memo": f"case:{case.id}",
                "payment_term": {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": due.isoformat()},
            },
            "invoicer": {"business_name": settings.merchant_name},
            "primary_recipients": [{"billing_info": {"email_address": case.customer.email}}],
            "items": [
                {
                    "name": case.description,
                    "quantity": "1",
                    "unit_amount": {"currency_code": case.currency, "value": f"{case.amount:.2f}"},
                }
            ],
        },
    )
    return body["id"]


def send_invoice(client: PayPalClient, invoice_id: str, *, case_id: str) -> None:
    """PayPal emails the customer. The kill switch is checked here, at the only place a send can happen."""
    if get_settings().kill_switch:
        raise SendingPaused()
    client.request(
        "POST",
        f"/v2/invoicing/invoices/{invoice_id}/send",
        request_id=f"case:{case_id}:invoice:send",
        json={"send_to_recipient": True, "send_to_invoicer": False},
    )


def payer_link(client: PayPalClient, invoice_id: str) -> str | None:
    body = client.request("GET", f"/v2/invoicing/invoices/{invoice_id}")
    return ((body.get("detail") or {}).get("metadata") or {}).get("recipient_view_url")
