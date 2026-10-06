"""Create the six demo customers and two closed example cases so the Floor is never empty (§9).

Idempotent: safe to run on every deploy. Example cases are added only to an empty database.
"""

from decimal import Decimal

from sqlalchemy import func, select

from vesper.cases import add_event, close_case, create_case
from vesper.db import SessionLocal
from vesper.demo_customers import ensure_demo_customers
from vesper.models import Case, Source


def main() -> None:
    with SessionLocal() as session:
        customers = {c.display_name.split()[0]: c for c in ensure_demo_customers(session)}
        if session.scalar(select(func.count()).select_from(Case)):
            session.commit()
            print("seed_demo: demo customers ensured; cases already exist, none added")
            return

        paid = create_case(
            session, source=Source.seeded, customer=customers["Lucía"], amount=Decimal("89.00"), currency="USD",
            description="Linen Throw", failure_code="INSTRUMENT_DECLINED",
        )
        add_event(session, paid, "webhook", "Example case created when this demo was deployed.")
        close_case(session, paid, "paid_elsewhere", "The order was paid another way. Closed.")

        refunded = create_case(
            session, source=Source.seeded, customer=customers["Sam"], amount=Decimal("29.00"), currency="USD",
            description="Monthly plan", failure_code="SUBSCRIPTION_PAYMENT_FAILED",
        )
        add_event(session, refunded, "webhook", "Example case created when this demo was deployed.")
        close_case(session, refunded, "refunded", "The order was refunded. Closed.")
        session.commit()
        print("seed_demo: demo customers ensured; two closed example cases added")


if __name__ == "__main__":
    main()
