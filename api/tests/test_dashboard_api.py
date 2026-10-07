from datetime import UTC, datetime
from decimal import Decimal

from tests.helpers import make_case
from vesper.models import Stage

AUTH = {"X-Dashboard-Token": "test-token"}


def seed(session_factory, n=1, **kw):
    with session_factory() as s:
        ids = [make_case(s, **kw).id for _ in range(n)]
        s.commit()
        return ids


def test_dashboard_routes_require_token(api):
    for path in ["/api/cases", "/api/metrics/today", "/api/rules", "/api/settings"]:
        assert api.get(path).status_code == 401
        assert api.get(path, headers={"X-Dashboard-Token": "wrong"}).status_code == 401


def test_health_is_public(api):
    assert api.get("/api/health").json()["env"] == "sandbox"


def test_case_list_newest_first_with_cursor(api, session_factory):
    ids = seed(session_factory, n=3)
    first = api.get("/api/cases?limit=2", headers=AUTH).json()
    assert len(first["cases"]) == 2 and first["next_cursor"]
    rest = api.get(f"/api/cases?limit=2&cursor={first['next_cursor']}", headers=AUTH).json()
    got = [c["id"] for c in first["cases"] + rest["cases"]]
    assert sorted(got) == sorted(ids) and len(set(got)) == 3 and rest["next_cursor"] is None


def test_case_detail_is_redacted(api, session_factory):
    [cid] = seed(session_factory)
    body = api.get(f"/api/cases/{cid}", headers=AUTH).json()
    text = str(body)
    assert "buyer@example.com" not in text and "Ruiz" not in text
    assert body["customer"]["first_name"] == "Marta" and body["place"] == "Madrid"
    assert body["events"][0]["text"].startswith("Payment failed")


def test_metrics_count_recovered_and_held_back(api, session_factory):
    [a, b, c] = seed(session_factory, n=3, amount=Decimal("40.00"))
    with session_factory() as s:
        from vesper.models import Case

        ra = s.get(Case, a)
        ra.stage, ra.recovered_at = Stage.recovered, datetime.now(UTC)
        rb = s.get(Case, b)
        rb.stage, rb.verdicts = Stage.held, {"verdicts": [], "final": {"outcome": "refuse", "refused_by": "R3"}}
        rc = s.get(Case, c)
        rc.stage, rc.verdicts = Stage.scheduled, {"verdicts": [], "final": {"outcome": "defer"}}
        s.commit()
    m = api.get("/api/metrics/today", headers=AUTH).json()
    assert m == {"recovered_total": "40.00", "recovered_count": 1, "held_back_count": 2, "queued_count": 1, "currency": "USD"}
    rows = {r["id"]: r for r in api.get("/api/cases", headers=AUTH).json()["cases"]}
    assert rows[b]["reason_short"] == "Consent required"


def test_rules_lists_eight(api):
    assert [r["id"] for r in api.get("/api/rules", headers=AUTH).json()["rules"]] == [f"R{i}" for i in range(1, 9)]


def test_settings_show_sandbox_buyer_only_in_demo_mode(api, monkeypatch):
    from vesper.config import get_settings

    assert api.get("/api/settings", headers=AUTH).json()["sandbox_buyer_email"] == "buyer@example.com"
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert api.get("/api/settings", headers=AUTH).json()["sandbox_buyer_email"] is None
