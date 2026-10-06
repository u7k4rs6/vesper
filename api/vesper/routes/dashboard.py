"""Read routes for the Floor, Case and Rules screens. All require X-Dashboard-Token."""

from datetime import UTC, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from vesper.auth import require_dashboard_token
from vesper.config import get_settings
from vesper.db import get_session
from vesper.models import Case, Stage
from vesper.pipeline.rules import RULE_NAMES, RULES

router = APIRouter(prefix="/api", dependencies=[Depends(require_dashboard_token)])

# Outcomes where the rules stopped or delayed a message the model wanted to send.
HELD_BACK_OUTCOMES = {"refuse", "defer"}


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite hands back naive UTC
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _today_start_utc() -> datetime:
    tz = ZoneInfo(get_settings().merchant_timezone)
    local_today = datetime.now(tz).date()
    return datetime.combine(local_today, time(0), tzinfo=tz).astimezone(UTC)


def _final(case: Case) -> dict:
    return (case.verdicts or {}).get("final") or {}


def _reason_short(case: Case) -> str | None:
    """For held and escalated rows: the refusing rule's name, or the event that explains it."""
    if case.stage not in (Stage.held, Stage.escalated):
        return None
    refused_by = _final(case).get("refused_by")
    if case.stage == Stage.held and refused_by:
        return RULE_NAMES[refused_by]
    last = next((e for e in reversed(case.events) if e.kind in ("held", "escalated")), None)
    return last.text.removeprefix("Checked: ").rstrip(".") if last else None


def _row(case: Case) -> dict:
    c = case.customer
    return {
        "id": case.id,
        "stage": case.stage.value,
        "source": case.source.value,
        "first_name": c.first_name,
        "place": c.city or c.country_code,
        "amount": f"{case.amount:.2f}",
        "currency": case.currency,
        "created_at": iso(case.created_at),
        "reason_short": _reason_short(case),
        "scheduled_for": (case.message or {}).get("scheduled_for") if case.stage == Stage.scheduled else None,
    }


@router.get("/metrics/today")
def metrics_today(session: Session = Depends(get_session)):
    settings = get_settings()
    start = _today_start_utc()
    recovered = session.execute(
        select(func.count(), func.coalesce(func.sum(Case.amount), 0)).where(
            Case.recovered_at >= start, Case.currency == settings.merchant_currency
        )
    ).one()
    today = session.scalars(select(Case).where(Case.created_at >= start)).all()
    held_back = sum(1 for c in today if _final(c).get("outcome") in HELD_BACK_OUTCOMES)
    queued = session.scalar(select(func.count()).select_from(Case).where(Case.stage == Stage.scheduled)) or 0
    return {
        "recovered_total": f"{Decimal(recovered[1]):.2f}",
        "recovered_count": recovered[0],
        "held_back_count": held_back,
        "queued_count": queued,
        "currency": settings.merchant_currency,
    }


@router.get("/cases")
def list_cases(
    stage: Stage | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    session: Session = Depends(get_session),
):
    q = select(Case).order_by(Case.created_at.desc(), Case.id.desc())
    if stage:
        q = q.where(Case.stage == stage)
    if cursor:
        anchor = session.get(Case, cursor)
        if anchor is None:
            raise HTTPException(status_code=400, detail="bad cursor")
        q = q.where(
            (Case.created_at < anchor.created_at) | ((Case.created_at == anchor.created_at) & (Case.id < anchor.id))
        )
    rows = session.scalars(q.limit(limit + 1)).all()
    page = rows[:limit]
    return {"cases": [_row(c) for c in page], "next_cursor": page[-1].id if len(rows) > limit else None}


@router.get("/cases/{case_id}")
def get_case(case_id: str, session: Session = Depends(get_session)):
    case = session.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    c = case.customer
    message = dict(case.message) if case.message else None
    if message:
        message.pop("template", None)  # the rendered note is what matters; the template is an internal detail
    return {
        **_row(case),
        "description": case.description,
        "failure_code": case.failure_code,
        "failure_category_hint": case.failure_category_hint.value,
        "closed_reason": case.closed_reason,
        "recovered_at": iso(case.recovered_at),
        "customer": {  # redacted: no email, no surname
            "first_name": c.first_name,
            "place": c.city or c.country_code,
            "country_code": c.country_code,
            "timezone": c.timezone,
            "locale": c.locale,
        },
        "diagnosis": case.diagnosis,
        "proposal": case.proposal,
        "verdicts": (case.verdicts or {}).get("verdicts"),
        "final": _final(case) or None,
        "message": message,
        "events": [{"at": iso(e.at), "kind": e.kind, "text": e.text} for e in case.events],
    }


@router.get("/rules")
def rules():
    return {"rules": [{"id": rid, "name": name, "description": text} for rid, name, text in RULES]}


@router.get("/settings")
def settings_route():
    s = get_settings()
    return {
        "approval_threshold": f"{s.approval_threshold:.2f}",
        "currency": s.merchant_currency,
        "contact_window": {"start": s.contact_window_start, "end": s.contact_window_end},
        "kill_switch": s.kill_switch,
        "merchant_name": s.merchant_name,
        "merchant_timezone": s.merchant_timezone,
    }
