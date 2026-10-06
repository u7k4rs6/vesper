import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from vesper.db import get_session
from vesper.paypal import webhooks
from vesper.paypal.client import get_client
from vesper.pipeline.run import run_case_in_new_session

router = APIRouter()
log = structlog.get_logger()


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, background: BackgroundTasks, session: Session = Depends(get_session)):
    raw = await request.body()
    headers = dict(request.headers)
    try:
        ok = webhooks.verify(get_client(), headers, raw)
    except webhooks.VerificationUnavailable:
        return _error(503, "verification_unavailable", "Could not verify the event; PayPal will retry.")
    if not ok:
        log.warning("webhook_rejected", transmission_id=headers.get("paypal-transmission-id"))
        return _error(400, "verification_failed", "Webhook signature could not be verified.")
    try:
        event = json.loads(raw)
    except ValueError:
        return _error(400, "bad_body", "Body is not JSON.")
    result = webhooks.handle(session, get_client(), event)
    session.commit()
    # The pipeline runs after the 200 goes out, so PayPal does not time out and retry.
    for case_id in result.new_case_ids:
        background.add_task(run_case_in_new_session, case_id)
    return {"ok": True}
