"""One asyncio task, every 15 s: send queued cases that are due, close cases past their TTL (§6.8)."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from vesper.cases import close_case
from vesper.config import get_settings
from vesper.db import SessionLocal
from vesper.models import TERMINAL_STAGES, Case, Stage
from vesper.pipeline.run import recheck_and_send

log = structlog.get_logger()
TICK_S = 15


def tick(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    settings = get_settings()
    with SessionLocal() as session:
        if not settings.kill_switch:
            for case in session.scalars(select(Case).where(Case.stage == Stage.scheduled)).all():
                due = (case.message or {}).get("scheduled_for")
                if due and datetime.fromisoformat(due) <= now:
                    try:
                        recheck_and_send(session, case, now)
                        session.commit()
                    except Exception:
                        session.rollback()
                        log.exception("scheduled_send_failed", case_id=case.id)

        cutoff = now - timedelta(hours=settings.case_ttl_hours)
        stale = session.scalars(
            select(Case).where(Case.stage.not_in(list(TERMINAL_STAGES)), Case.created_at < cutoff)
        ).all()
        for case in stale:
            close_case(session, case, "expired", "Closed: no payment within the time limit.")
        session.commit()


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("scheduler_tick_failed")
        await asyncio.sleep(TICK_S)
