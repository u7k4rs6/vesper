"""The six demo customers (§7). Every one's email is SANDBOX_BUYER_EMAIL so a judge can pay the invoice.

The spread of timezones means at any hour at least one is outside the 09:00–20:00 window, and Chen
is opted out, so R3 and R4 are visibly exercised.
"""

from itertools import count

from sqlalchemy import select
from sqlalchemy.orm import Session

from vesper.config import get_settings
from vesper.models import Customer

DEMO_CUSTOMERS = [
    dict(display_name="Marta Ruiz", country_code="ES", city="Madrid", timezone="Europe/Madrid", locale="es-ES"),
    dict(display_name="Rohan Iyer", country_code="IN", city="Bengaluru", timezone="Asia/Kolkata", locale="hi-IN"),
    dict(display_name="Alex Moore", country_code="US", city="Austin", timezone="America/Chicago", locale="en-US"),
    dict(display_name="Chen Wei", country_code="SG", city="Singapore", timezone="Asia/Singapore", locale="en-SG",
         opted_out=True),
    dict(display_name="Lucía Gómez", country_code="MX", city="Mexico City", timezone="America/Mexico_City",
         locale="es-MX"),
    dict(display_name="Sam Taylor", country_code="NZ", city="Auckland", timezone="Pacific/Auckland", locale="en-NZ"),
]

_rotation = count()


def ensure_demo_customers(session: Session) -> list[Customer]:
    email = get_settings().sandbox_buyer_email
    existing = {c.display_name: c for c in session.scalars(select(Customer)).all()}
    out = []
    for spec in DEMO_CUSTOMERS:
        c = existing.get(spec["display_name"])
        if c is None:
            c = Customer(**({"email": email, "email_consent": True, "opted_out": False} | spec))
            session.add(c)
        elif c.email != email:
            c.email = email  # follow SANDBOX_BUYER_EMAIL when the judge's buyer account changes
        out.append(c)
    session.flush()
    return out


def next_demo_customer(session: Session) -> Customer:
    customers = ensure_demo_customers(session)
    return customers[next(_rotation) % len(customers)]
