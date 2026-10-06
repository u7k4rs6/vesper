"""Static checks that hold the safety properties in place (04_SECURITY.md §6)."""

import re
from pathlib import Path

import pytest

from vesper.config import Settings
from vesper.models import CaseEvent

API = Path(__file__).resolve().parents[1]
SOURCES = [p for p in API.rglob("*.py") if ".venv" not in p.parts and "tests" not in p.parts]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_no_live_paypal_host():
    live = re.compile(r"api-m\.paypal\.com|api\.paypal\.com")
    offenders = [str(p) for p in API.rglob("*") if p.is_file() and ".venv" not in p.parts
                 and "__pycache__" not in p.parts and p.suffix in {".py", ".toml", ".ini", ".md", ".yaml", ".json", ".example"}
                 and live.search(_read(p))]
    assert offenders == []


def test_paypal_env_must_be_sandbox():
    with pytest.raises(ValueError):
        Settings(paypal_env="live")


def test_case_events_has_no_update_or_delete():
    pattern = re.compile(r"(update|delete)\(\s*CaseEvent|CaseEvent\)\.(update|delete)|(UPDATE|DELETE FROM)\s+case_events", re.I)
    offenders = [str(p) for p in SOURCES if pattern.search(_read(p))]
    assert offenders == []


def test_case_events_rows_cannot_be_modified(session):
    from vesper.cases import add_event, create_case
    from vesper.demo_customers import next_demo_customer
    from vesper.models import Source

    case = create_case(session, source=Source.seeded, customer=next_demo_customer(session), amount=1,
                       currency="USD", description="x", failure_code="INSTRUMENT_DECLINED")
    ev = add_event(session, case, "webhook", "original")
    session.flush()
    ev.text = "rewritten"
    with pytest.raises(RuntimeError, match="append-only"):
        session.flush()
    session.rollback()


def test_no_capture_outside_demo_store():
    capture = re.compile(r"/v2/checkout/orders/[^\"']*/capture|/v2/payments/authorizations")
    offenders = [str(p.relative_to(API)) for p in SOURCES if capture.search(_read(p))]
    assert offenders == ["vesper/paypal/orders.py"]
    importers = [str(p.relative_to(API)) for p in SOURCES if re.search(r"paypal\s+import\s+.*\borders\b|paypal\.orders", _read(p))]
    assert sorted(importers) == ["vesper/paypal/webhooks.py", "vesper/routes/store.py"]


def _imports_provider(src: str) -> bool:
    return re.search(r"from vesper\.llm(\.provider)? import|import vesper\.llm\.provider|from vesper\.llm import provider", src) is not None


def test_llm_called_from_two_sites_only():
    sites = sorted(str(p.relative_to(API)) for p in SOURCES if _imports_provider(_read(p)) and "vesper/llm/" not in str(p))
    assert sites == ["vesper/pipeline/diagnose.py", "vesper/pipeline/propose.py"]
    # Nobody talks to a model SDK directly except the provider module.
    direct = [str(p.relative_to(API)) for p in SOURCES if re.search(r"^\s*(import anthropic|from anthropic)", _read(p), re.M)]
    assert direct == ["vesper/llm/provider.py"]


def test_evidence_packet_fields_are_exact():
    from vesper.pipeline.evidence import CustomerEvidence, EvidencePacket

    assert set(EvidencePacket.model_fields) == {
        "source", "failure_code", "failure_category_hint", "amount", "currency", "description",
        "customer", "prior_touches_this_case", "prior_touches_30d", "merchant_name",
    }
    assert set(CustomerEvidence.model_fields) == {
        "first_name", "country_code", "timezone", "local_time_now", "locale", "email_consent", "opted_out",
    }


def test_send_invoice_has_one_call_site():
    calls = [str(p.relative_to(API)) for p in SOURCES if re.search(r"\bsend_invoice\(", _read(p))
             and "def send_invoice(" not in _read(p)]
    assert calls == ["vesper/sending.py"]


def test_toolkit_allowlist_has_no_write_tools():
    # The Agent Toolkit is Phase 2; until it lands, nothing may import it at all.
    offenders = [str(p.relative_to(API)) for p in SOURCES if re.search(r"paypal_agent_toolkit|agent_toolkit", _read(p))]
    assert offenders == []
