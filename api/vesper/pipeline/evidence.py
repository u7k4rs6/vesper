"""What the model is allowed to see (§6.2). Nothing else: no email, full name, PayPal ids, URLs, or payloads."""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from vesper.models import Case, Customer

_UNSAFE = re.compile(r"[\x00-\x1f\x7f<>]")
MAX_DATA_LEN = 80


def sanitise(text: str, limit: int = MAX_DATA_LEN) -> str:
    """Untrusted strings: strip control characters and angle brackets, cap the length."""
    return _UNSAFE.sub("", text).strip()[:limit]


class CustomerEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str
    country_code: str
    timezone: str
    local_time_now: str
    locale: str
    email_consent: bool
    opted_out: bool


class EvidencePacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    failure_code: str
    failure_category_hint: str
    amount: str
    currency: str
    description: str
    customer: CustomerEvidence
    prior_touches_this_case: int
    prior_touches_30d: int
    merchant_name: str


def build_packet(
    case: Case, customer: Customer, *, touches_case: int, touches_30d: int, merchant: str, now: datetime
) -> EvidencePacket:
    local = now.astimezone(ZoneInfo(customer.timezone))
    return EvidencePacket(
        source=case.source.value,
        failure_code=case.failure_code,
        failure_category_hint=case.failure_category_hint.value,
        amount=f"{case.amount:.2f}",
        currency=case.currency,
        description=sanitise(case.description),
        customer=CustomerEvidence(
            first_name=sanitise(customer.first_name),
            country_code=customer.country_code,
            timezone=customer.timezone,
            local_time_now=local.strftime("%H:%M"),
            locale=customer.locale,
            email_consent=customer.email_consent,
            opted_out=customer.opted_out,
        ),
        prior_touches_this_case=touches_case,
        prior_touches_30d=touches_30d,
        merchant_name=merchant,
    )


def as_prompt_block(packet: EvidencePacket) -> str:
    return "<data>" + packet.model_dump_json() + "</data>"
