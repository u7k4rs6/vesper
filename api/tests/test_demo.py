import json

import pytest
from sqlalchemy import select

from vesper.config import get_settings
from vesper.models import Case, Hint, Source

AUTH = {"X-Dashboard-Token": "test-token"}


@pytest.fixture
def simulate(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_fail_strategy", "simulate_event")


@pytest.fixture(autouse=True)
def no_pipeline(monkeypatch):
    # The pipeline has its own tests; here we only check what the button creates.
    from vesper.routes import demo

    monkeypatch.setattr(demo, "run_case_in_new_session", lambda case_id: None)


@pytest.mark.parametrize(
    "kind,source_amount,hint",
    [("subscription", "29.00", Hint.soft), ("capture_denied", "89.00", Hint.hard)],
)
def test_internal_strategy_seeds_a_case_and_can_repeat(api, session_factory, kind, source_amount, hint):
    for _ in range(2):  # repeatable, unlike PayPal's fixed-id simulated events
        r = api.post("/api/demo/fail", json={"kind": kind}, headers=AUTH)
        assert r.status_code == 200 and r.json()["strategy"] == "internal"
    with session_factory() as s:
        made = s.scalars(select(Case)).all()
    assert len(made) == 2
    assert all(c.source == Source.seeded and str(c.amount) == source_amount and c.failure_category_hint == hint for c in made)


def test_fail_a_payment_asks_paypal_to_simulate_the_event(api, paypal, simulate):
    route = paypal.post("/v1/notifications/simulate-event").respond(202, json={"id": "WH-SIM"})
    r = api.post("/api/demo/fail", json={"kind": "subscription"}, headers=AUTH)
    assert r.status_code == 200
    body = json.loads(route.calls.last.request.content)
    assert body == {"webhook_id": "WH-TEST", "event_type": "BILLING.SUBSCRIPTION.PAYMENT.FAILED"}


def test_capture_denied_asks_for_the_v2_payload(api, paypal, simulate):
    route = paypal.post("/v1/notifications/simulate-event").respond(202, json={})
    api.post("/api/demo/fail", json={"kind": "capture_denied"}, headers=AUTH)
    assert json.loads(route.calls.last.request.content)["resource_version"] == "2.0"


def test_fail_a_payment_requires_token(api):
    assert api.post("/api/demo/fail", json={"kind": "subscription"}).status_code == 401


def test_fail_a_payment_rejects_unknown_kind(api):
    assert api.post("/api/demo/fail", json={"kind": "refund"}, headers=AUTH).status_code == 422


def test_fail_a_payment_is_rate_limited_per_client(api):
    codes = [api.post("/api/demo/fail", json={"kind": "capture_denied"},
                      headers={**AUTH, "X-Forwarded-For": "203.0.113.7"}).status_code for _ in range(7)]
    assert codes[:6] == [200] * 6 and codes[6] == 429
    # A different browser is not blocked by the first one's limit.
    other = api.post("/api/demo/fail", json={"kind": "capture_denied"}, headers={**AUTH, "X-Forwarded-For": "198.51.100.9"})
    assert other.status_code == 200
