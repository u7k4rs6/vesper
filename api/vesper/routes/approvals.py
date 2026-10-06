"""Approve or decline a case waiting on the approval threshold (R7). Both are idempotent-safe: a replay after
the case has moved on returns 409."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from vesper.auth import require_dashboard_token
from vesper.cases import add_event
from vesper.db import get_session
from vesper.models import Case, Stage
from vesper.pipeline.run import recheck_and_send

router = APIRouter(prefix="/api/cases", dependencies=[Depends(require_dashboard_token)])


def _awaiting(session: Session, case_id: str) -> Case:
    # Lock only the cases row: Postgres refuses FOR UPDATE on the outer-joined customer.
    case = session.scalars(select(Case).where(Case.id == case_id).with_for_update(of=Case)).first()
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    if case.stage != Stage.awaiting_approval:
        raise HTTPException(status_code=409, detail="case is not waiting for approval")
    return case


@router.post("/{case_id}/approve")
def approve(case_id: str, session: Session = Depends(get_session)):
    case = _awaiting(session, case_id)
    case.stage = Stage.checked  # claim it before the slow PayPal calls, so a double click gets a 409
    add_event(session, case, "approved", "Approved by you.")
    session.commit()
    recheck_and_send(session, case, datetime.now(UTC))
    session.commit()
    return {"stage": case.stage.value}


@router.post("/{case_id}/decline")
def decline(case_id: str, session: Session = Depends(get_session)):
    case = _awaiting(session, case_id)
    case.stage = Stage.held
    add_event(session, case, "declined", "Declined by you. Nothing was sent.")
    session.commit()
    return {"stage": case.stage.value}
