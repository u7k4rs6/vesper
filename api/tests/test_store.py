from sqlalchemy import select

from vesper.models import Case, Hint, Source

ORDER = {
    "id": "ORDER-9",
    "status": "APPROVED",
    "payer": {"email_address": "judge@example.com", "name": {"given_name": "Marta", "surname": "Ruiz"},
              "address": {"country_code": "ES"}},
}


def test_forced_decline_creates_soft_case_with_payer(api, paypal, session_factory):
    capture = paypal.post("/v2/checkout/orders/ORDER-9/capture").respond(
        422, json={"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "INSTRUMENT_DECLINED"}]}
    )
    paypal.get("/v2/checkout/orders/ORDER-9").respond(200, json=ORDER)
    r = api.post("/api/demo/store/orders/ORDER-9/capture?force_decline=true")
    assert r.status_code == 200 and r.json()["status"] == "failed"
    assert '"mock_application_codes": "INSTRUMENT_DECLINED"' in capture.calls.last.request.headers["PayPal-Mock-Response"]
    with session_factory() as s:
        case = s.scalars(select(Case)).one()
        assert case.id == r.json()["case_id"]
        assert case.source == Source.checkout_decline and case.failure_category_hint == Hint.soft
        assert case.customer.first_name == "Marta" and case.customer.timezone == "Europe/Madrid"


def test_capture_without_force_decline_sends_no_mock_header(api, paypal):
    capture = paypal.post("/v2/checkout/orders/ORDER-9/capture").respond(
        201, json={"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [{"id": "C", "status": "COMPLETED"}]}}]}
    )
    r = api.post("/api/demo/store/orders/ORDER-9/capture?force_decline=false")
    assert r.json() == {"status": "completed"}
    assert "PayPal-Mock-Response" not in capture.calls.last.request.headers


def test_refused_transaction_creates_hard_case(api, paypal, session_factory):
    paypal.post("/v2/checkout/orders/ORDER-9/capture").respond(
        422, json={"details": [{"issue": "TRANSACTION_REFUSED"}]}
    )
    paypal.get("/v2/checkout/orders/ORDER-9").respond(200, json=ORDER)
    api.post("/api/demo/store/orders/ORDER-9/capture")
    with session_factory() as s:
        assert s.scalars(select(Case)).one().failure_category_hint == Hint.hard


def test_unrecognised_error_creates_no_case(api, paypal, session_factory):
    paypal.post("/v2/checkout/orders/ORDER-9/capture").respond(422, json={"details": [{"issue": "ORDER_NOT_APPROVED"}]})
    r = api.post("/api/demo/store/orders/ORDER-9/capture")
    assert r.status_code == 502
    with session_factory() as s:
        assert s.scalars(select(Case)).all() == []
