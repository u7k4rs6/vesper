"""Tables from 02_TECHNICAL_ARCHITECTURE.md §3. Money is Numeric(12,2); times are UTC."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Numeric, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vesper.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class Source(StrEnum):
    checkout_decline = "checkout_decline"
    capture_denied = "capture_denied"
    subscription_failed = "subscription_failed"
    capture_pending = "capture_pending"
    checkout_abandoned = "checkout_abandoned"
    seeded = "seeded"


class Hint(StrEnum):
    soft = "soft"
    hard = "hard"
    pending = "pending"
    unknown = "unknown"


class Stage(StrEnum):
    failed = "failed"
    diagnosed = "diagnosed"
    proposed = "proposed"
    checked = "checked"
    awaiting_approval = "awaiting_approval"
    scheduled = "scheduled"
    sent = "sent"
    waiting = "waiting"
    recovered = "recovered"
    held = "held"
    escalated = "escalated"
    closed = "closed"


TERMINAL_STAGES = {Stage.recovered, Stage.held, Stage.escalated, Stage.closed}


def _enum(e):
    return Enum(e, native_enum=False, length=32, values_callable=lambda x: [m.value for m in x])


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    country_code: Mapped[str] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(35))
    email_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def first_name(self) -> str:
        return self.display_name.split()[0] if self.display_name.strip() else ""


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source: Mapped[Source] = mapped_column(_enum(Source))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str] = mapped_column(String(200))
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    paypal_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paypal_invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    failure_code: Mapped[str] = mapped_column(String(64))
    failure_category_hint: Mapped[Hint] = mapped_column(_enum(Hint))
    stage: Mapped[Stage] = mapped_column(_enum(Stage), default=Stage.failed, index=True)
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    diagnosis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verdicts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    message: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[Customer] = relationship(lazy="joined")
    events: Mapped[list["CaseEvent"]] = relationship(order_by="CaseEvent.at", lazy="selectin")


class CaseEvent(Base):
    """Append-only. There is no update or delete path; see test_case_events_has_no_update_or_delete."""

    __tablename__ = "case_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    kind: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String(500))
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


@event.listens_for(CaseEvent, "before_update")
@event.listens_for(CaseEvent, "before_delete")
def _case_events_are_append_only(mapper, connection, target):
    raise RuntimeError("case_events is append-only")


class Touch(Base):
    __tablename__ = "touches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
