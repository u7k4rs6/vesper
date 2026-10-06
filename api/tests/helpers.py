from decimal import Decimal

from vesper.cases import create_case
from vesper.models import Customer, Source


def make_customer(session, **overrides) -> Customer:
    fields = dict(
        display_name="Marta Ruiz", email="buyer@example.com", country_code="ES", city="Madrid",
        timezone="Europe/Madrid", locale="es-ES", email_consent=True, opted_out=False,
    )
    fields.update(overrides)
    c = Customer(**fields)
    session.add(c)
    session.flush()
    return c


def make_case(session, *, amount=Decimal("89.00"), failure_code="INSTRUMENT_DECLINED", customer=None, **kw):
    return create_case(
        session,
        source=kw.pop("source", Source.checkout_decline),
        customer=customer or make_customer(session),
        amount=amount,
        currency="USD",
        description="Linen Throw",
        failure_code=failure_code,
        paypal_order_id=kw.pop("paypal_order_id", None),
    )
