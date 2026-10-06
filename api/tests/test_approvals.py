from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from tests.helpers import make_case
from vesper import sending
from vesper.models import Case, Stage
from vesper.pipeline import run as run_module
from vesper.pipeline.run import run_case

AUTH = {"X-Dashboard-Token": "test-token"}
MIDDAY = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(sending.time, "sleep", lambda s: None)


@pytest.fixture
def invoicing_ok(paypal):
    paypal.post("/v2/invoicing/generate-next-invoice-number").respond(200, json={"invoice_number": "7"})
    paypal.post("/v2/invoicing/invoices").respond(201, json={"id": "INV2-BIG"})
    send = paypal.post("/v2/invoicing/invoices/INV2-BIG/send").respond(202, json={})
    paypal.get("/v2/invoicing/invoices/INV2-BIG").respond(200, json={"detail": {"metadata": {}}})
    return send


def awaiting_case(session_factory) -> str:
    with session_factory() as s:
        case = make_case(s, amount=Decimal("640.00"))
        s.commit()
        run_case(s, case.id, MIDDAY)
        assert s.get(Case, case.id).stage == Stage.awaiting_approval
        return case.id


def freeze_clock(monkeypatch, when: datetime):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return when

    from vesper.routes import approvals

    monkeypatch.setattr(approvals, "datetime", Clock)


def test_approve_sends_when_window_is_open(api, session_factory, invoicing_ok, monkeypatch):
    cid = awaiting_case(session_factory)
    freeze_clock(monkeypatch, MIDDAY)
    r = api.post(f"/api/cases/{cid}/approve", headers=AUTH)
    assert r.status_code == 200 and r.json() == {"stage": "sent"}
    assert invoicing_ok.called


def test_approve_at_night_queues_for_nine(api, session_factory, invoicing_ok, monkeypatch):
    cid = awaiting_case(session_factory)
    freeze_clock(monkeypatch, datetime(2026, 10, 5, 23, 0, tzinfo=UTC))  # 01:00 in Madrid
    r = api.post(f"/api/cases/{cid}/approve", headers=AUTH)
    assert r.json() == {"stage": "scheduled"}
    assert not invoicing_ok.called


def test_replayed_approval_returns_409(api, session_factory, invoicing_ok, monkeypatch):
    cid = awaiting_case(session_factory)
    freeze_clock(monkeypatch, MIDDAY)
    assert api.post(f"/api/cases/{cid}/approve", headers=AUTH).status_code == 200
    assert api.post(f"/api/cases/{cid}/approve", headers=AUTH).status_code == 409
    assert api.post(f"/api/cases/{cid}/decline", headers=AUTH).status_code == 409


def test_decline_holds_and_sends_nothing(api, session_factory, invoicing_ok):
    cid = awaiting_case(session_factory)
    r = api.post(f"/api/cases/{cid}/decline", headers=AUTH)
    assert r.json() == {"stage": "held"}
    assert not invoicing_ok.called
    with session_factory() as s:
        assert s.get(Case, cid).events[-1].text == "Declined by you. Nothing was sent."


def test_approval_routes_require_token(api, session_factory):
    cid = awaiting_case(session_factory)
    assert api.post(f"/api/cases/{cid}/approve").status_code == 401
    assert api.post(f"/api/cases/{cid}/decline").status_code == 401


def test_unknown_case_is_404(api):
    assert api.post("/api/cases/nope/approve", headers=AUTH).status_code == 404
