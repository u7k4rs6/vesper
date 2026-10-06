import inspect
import json
from datetime import date
from decimal import Decimal

import pytest

from vesper import sending
from vesper.paypal import invoicing
from vesper.pipeline import diagnose, evidence, messaging, propose, rules, run, taxonomy

PIPELINE_MODULES = [diagnose, propose, evidence, messaging, rules, run, taxonomy, sending, invoicing]
MONEY_WORDS = {"amount", "value", "price", "total", "unit_amount", "sum"}
# Display formatters: they turn the case row's amount into text and never reach an invoice body.
FORMATTERS = {"vesper.pipeline.messaging.render", "vesper.pipeline.rules._money"}


def test_no_pipeline_function_accepts_an_amount():
    offenders = []
    for module in PIPELINE_MODULES:
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            if fn.__module__ != module.__name__ or f"{module.__name__}.{name}" in FORMATTERS:
                continue
            params = set(inspect.signature(fn).parameters)
            if params & MONEY_WORDS:
                offenders.append(f"{module.__name__}.{name}")
    assert offenders == []


def test_invoice_body_amount_equals_case_amount(session, paypal):
    from tests.helpers import make_case

    case = make_case(session, amount=Decimal("89.00"))
    paypal.post("/v2/invoicing/generate-next-invoice-number").respond(200, json={"invoice_number": "0042"})
    create = paypal.post("/v2/invoicing/invoices").respond(
        201, json={"id": "INV2-TEST", "detail": {"metadata": {"recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#INV2-TEST"}}}
    )
    from vesper.paypal.client import get_client

    invoice_id = invoicing.create_invoice(get_client(), case, "Hola Marta", due=date(2026, 10, 12))
    body = json.loads(create.calls.last.request.content)
    assert invoice_id == "INV2-TEST"
    assert body["items"] == [
        {"name": case.description, "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "89.00"}}
    ]
    assert body["detail"]["note"] == "Hola Marta"
    assert body["detail"]["memo"] == f"case:{case.id}"
    assert body["detail"]["payment_term"] == {"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "2026-10-12"}
    assert body["primary_recipients"][0]["billing_info"]["email_address"] == case.customer.email
    assert create.calls.last.request.headers["PayPal-Request-Id"] == f"case:{case.id}:invoice:create"


def test_kill_switch_blocks_all_sends(session, paypal, monkeypatch):
    from vesper.config import get_settings
    from vesper.paypal.client import get_client

    monkeypatch.setattr(get_settings(), "kill_switch", True)
    route = paypal.post("/v2/invoicing/invoices/INV2-X/send").respond(202, json={})
    with pytest.raises(invoicing.SendingPaused):
        invoicing.send_invoice(get_client(), "INV2-X", case_id="c1")
    assert not route.called
