"""Full loop against PayPal sandbox and the configured model, no human needed:
seeded case -> diagnose -> propose -> rules -> real PayPal invoice sent.

Starts from a seeded case rather than a forced capture decline, because capture lives in paypal/orders.py,
which test_no_capture_outside_demo_store reserves for the demo store. The forced decline is exercised by the
Store page. Exits non-zero if any step fails; refuses to run without credentials. Sends one real sandbox
invoice to SANDBOX_BUYER_EMAIL, using whichever demo customer is currently inside the contact window.
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from vesper.cases import create_case
from vesper.config import get_settings
from vesper.db import SessionLocal
from vesper.demo_customers import ensure_demo_customers
from vesper.models import Case, Source, Stage, Touch
from vesper.pipeline.rules import CUSTOMER_TOUCH_CAP_30D, next_window_open
from vesper.pipeline.run import policy, run_case


def fail(step: str, detail: str) -> int:
    print(f"FAIL  {step}: {detail}", file=sys.stderr)
    return 1


def main() -> int:
    s = get_settings()
    missing = [k for k, v in {
        "PAYPAL_CLIENT_ID": s.paypal_client_id, "PAYPAL_CLIENT_SECRET": s.paypal_client_secret,
        "SANDBOX_BUYER_EMAIL": s.sandbox_buyer_email, "LLM_API_KEY": s.llm_api_key or s.llm_provider == "fixture",
    }.items() if not v]
    if missing:
        return fail("setup", f"missing {', '.join(missing)}; this script only runs with sandbox credentials")
    if s.kill_switch:
        return fail("setup", "KILL_SWITCH is on, so no invoice can be sent")

    now = datetime.now(UTC)
    with SessionLocal() as session:
        # A customer the rules would allow: consented, inside the contact window, under the 30-day cap.
        def touches_30d(c) -> int:
            return session.scalar(select(func.count()).select_from(Touch).where(
                Touch.customer_id == c.id, Touch.sent_at >= now - timedelta(days=30))) or 0

        awake = [c for c in ensure_demo_customers(session)
                 if not c.opted_out and next_window_open(now, c.timezone, policy()) is None
                 and touches_30d(c) < CUSTOMER_TOUCH_CAP_30D]
        if not awake:
            return fail("customer", "no demo customer is inside the contact window and under the 30-day cap; "
                                    "try again later")
        case = create_case(session, source=Source.seeded, customer=awake[0], amount=Decimal("89.00"),
                           currency="USD", description="Linen Throw", failure_code="INSTRUMENT_DECLINED")
        session.commit()
        print(f"ok    case created            {case.id} ({awake[0].first_name}, {awake[0].city})")

        run_case(session, case.id)
        case = session.get(Case, case.id)
        session.refresh(case)
        for e in case.events:
            print(f"      {e.text}")
        if case.stage != Stage.sent:
            return fail("pipeline", f"expected stage sent, got {case.stage.value}")
        print(f"ok    invoice sent            {case.paypal_invoice_id}")
        print(f"      payer link              {(case.message or {}).get('payer_link')}")
    print("PASS  case -> diagnosis -> checks -> invoice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
