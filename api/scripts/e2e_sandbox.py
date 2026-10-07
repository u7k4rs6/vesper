"""Full loop against PayPal sandbox and the configured model, no human needed (§9):
order -> forced INSTRUMENT_DECLINED capture -> case -> diagnose -> propose -> rules -> invoice sent.

Exits non-zero if any step fails. Refuses to run without credentials. Sends one real sandbox invoice
to SANDBOX_BUYER_EMAIL, using whichever demo customer is currently inside the contact window.
"""

import sys
from datetime import UTC, datetime
from decimal import Decimal

from vesper.cases import create_case
from vesper.config import get_settings
from vesper.db import SessionLocal
from vesper.demo_customers import ensure_demo_customers
from vesper.models import Case, Source, Stage
from vesper.paypal import orders
from vesper.paypal.client import get_client
from vesper.pipeline.rules import next_window_open
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

    client = get_client()
    order_id = orders.create_order(client, Decimal("89.00"), "USD", "Linen Throw")
    print(f"ok    order created           {order_id}")
    outcome = orders.capture_order(client, order_id, force_decline=True)
    if outcome.status != "failed" or outcome.failure_code != "INSTRUMENT_DECLINED":
        return fail("forced decline", f"expected INSTRUMENT_DECLINED, got {outcome.status} {outcome.failure_code}")
    print("ok    capture declined         INSTRUMENT_DECLINED (sandbox negative test)")

    now = datetime.now(UTC)
    with SessionLocal() as session:
        awake = [c for c in ensure_demo_customers(session)
                 if not c.opted_out and next_window_open(now, c.timezone, policy()) is None]
        if not awake:
            return fail("customer", "no demo customer is inside the contact window right now; try again later")
        case = create_case(session, source=Source.checkout_decline, customer=awake[0], amount=Decimal("89.00"),
                           currency="USD", description="Linen Throw", failure_code="INSTRUMENT_DECLINED",
                           paypal_order_id=order_id)
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
    print("PASS  failure -> diagnosis -> checks -> invoice")
    return 0


if __name__ == "__main__":
    sys.exit(main())
