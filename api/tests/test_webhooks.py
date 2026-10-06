import json

from sqlalchemy import select

from vesper.models import Case, CaseEvent, Hint, Source, Stage

HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT",
    "PAYPAL-TRANSMISSION-ID": "tx-1",
    "PAYPAL-TRANSMISSION-SIG": "sig",
    "PAYPAL-TRANSMISSION-TIME": "2026-10-05T10:00:00Z",
}


def denied_event(event_id="WH-EVT-1", order_id="ORDER-1"):
    return {
        "id": event_id,
        "event_type": "PAYMENT.CAPTURE.DENIED",
        "resource": {
            "id": "CAP-1",
            "status": "DECLINED",
            "amount": {"value": "89.00", "currency_code": "USD"},
            "supplementary_data": {"related_ids": {"order_id": order_id}},
        },
    }


def verified(paypal, status="SUCCESS"):
    return paypal.post("/v1/notifications/verify-webhook-signature").respond(200, json={"verification_status": status})


def post(api, event, headers=HEADERS):
    return api.post("/webhooks/paypal", content=json.dumps(event).encode(), headers=headers)


def cases(session_factory):
    with session_factory() as s:
        return s.scalars(select(Case)).all()


def test_webhook_without_valid_signature_is_rejected(api, paypal, session_factory):
    verified(paypal, status="FAILURE")
    r = post(api, denied_event())
    assert r.status_code == 400
    assert cases(session_factory) == []


def test_webhook_missing_transmission_headers_is_rejected_without_calling_paypal(api, paypal, session_factory):
    route = verified(paypal)
    r = post(api, denied_event(), headers={})
    assert r.status_code == 400 and not route.called
    assert cases(session_factory) == []


def test_verification_outage_returns_503_so_paypal_retries(api, paypal, session_factory):
    paypal.post("/v1/notifications/verify-webhook-signature").respond(503, json={"name": "SERVICE_UNAVAILABLE"})
    r = post(api, denied_event())
    assert r.status_code == 503
    assert cases(session_factory) == []


def test_verification_sends_raw_body_byte_for_byte(api, paypal):
    route = verified(paypal)
    raw = b'{"id": "WH-RAW",   "event_type": "UNHANDLED.EVENT", "resource": {}}'
    api.post("/webhooks/paypal", content=raw, headers=HEADERS)
    sent = route.calls.last.request.content
    assert sent.endswith(b'"webhook_event": ' + raw + b"}")
    body = json.loads(sent)
    assert body["webhook_id"] == "WH-TEST" and body["transmission_id"] == "tx-1"


def test_capture_denied_creates_hard_case(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={"name": "RESOURCE_NOT_FOUND"})
    assert post(api, denied_event()).status_code == 200
    [case] = cases(session_factory)
    assert case.source == Source.capture_denied
    assert case.failure_category_hint == Hint.hard
    assert case.stage == Stage.failed
    assert str(case.amount) == "89.00"
    assert case.customer.email == "buyer@example.com"  # demo rotation for simulated events


def test_duplicate_webhook_is_acknowledged_once(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={})
    assert post(api, denied_event()).status_code == 200
    assert post(api, denied_event()).status_code == 200
    assert len(cases(session_factory)) == 1


def test_capture_completed_closes_open_case_as_paid_elsewhere(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={})
    pending = denied_event("WH-P", "ORDER-1") | {"event_type": "PAYMENT.CAPTURE.PENDING"}
    post(api, pending)
    completed = denied_event("WH-C", "ORDER-1") | {"event_type": "PAYMENT.CAPTURE.COMPLETED"}
    post(api, completed)
    [case] = cases(session_factory)
    assert case.stage == Stage.closed and case.closed_reason == "paid_elsewhere"


def test_subscription_failure_uses_demo_amount_in_demo_mode(api, paypal, session_factory):
    verified(paypal)
    event = {"id": "WH-S", "event_type": "BILLING.SUBSCRIPTION.PAYMENT.FAILED", "resource": {"id": "I-SUB"}}
    post(api, event)
    [case] = cases(session_factory)
    assert case.source == Source.subscription_failed
    assert case.failure_category_hint == Hint.soft
    assert str(case.amount) == "29.00"


def test_invoice_paid_recovers_case(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={})
    post(api, denied_event())
    with session_factory() as s:
        case = s.scalars(select(Case)).one()
        case.paypal_invoice_id = "INV2-AAAA"
        s.commit()
    post(api, {"id": "WH-I", "event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "INV2-AAAA"}})
    [case] = cases(session_factory)
    assert case.stage == Stage.recovered and case.recovered_at is not None


def test_dispute_freezes_case(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={})
    post(api, denied_event())
    post(api, {"id": "WH-D", "event_type": "CUSTOMER.DISPUTE.CREATED",
               "resource": {"disputed_transactions": [{"seller_transaction_id": "CAP-1"}]}})
    [case] = cases(session_factory)
    assert case.frozen


def test_events_are_written_to_the_timeline(api, paypal, session_factory):
    verified(paypal)
    paypal.get("/v2/checkout/orders/ORDER-1").respond(404, json={})
    post(api, denied_event())
    with session_factory() as s:
        kinds = [e.kind for e in s.scalars(select(CaseEvent).order_by(CaseEvent.at))]
    assert kinds == ["created", "webhook"]


def test_simulated_capture_without_v2_amount_still_creates_demo_case(api, paypal, session_factory):
    verified(paypal)
    event = {"id": "WH-V1", "event_type": "PAYMENT.CAPTURE.DENIED",
             "resource": {"id": "CAP-V1", "amount": {"total": "7.47", "currency": "USD"}}}
    assert post(api, event).status_code == 200
    [case] = cases(session_factory)
    assert str(case.amount) == "89.00" and case.description == "Linen Throw"
