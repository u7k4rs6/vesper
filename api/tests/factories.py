from dataclasses import replace
from datetime import time
from decimal import Decimal

from vesper.models import Hint
from vesper.pipeline.rules import Policy, RuleInput
from vesper.pipeline.schemas import Proposal

POLICY = Policy(approval_threshold=Decimal("500.00"), window_start=time(9), window_end=time(20))

MARTA = RuleInput(
    hint=Hint.soft,
    amount=Decimal("89.00"),
    currency="USD",
    frozen=False,
    closed_reason=None,
    first_name="Marta",
    place="Madrid",
    timezone="Europe/Madrid",
    locale="es-ES",
    email_consent=True,
    opted_out=False,
    touches_this_case=0,
    touches_30d=0,
)

GOOD_ES = (
    "Hola {first_name}, no pudimos completar el pago de {amount} por {description}. "
    "Si aún lo quieres, puedes pagar con esta factura hasta el {due_date}. Gracias, {merchant}"
)


def send(template: str = GOOD_ES, language: str = "es") -> Proposal:
    return Proposal(action="SEND_INVOICE", rationale="Soft decline.", message_template=template, language=language)


def marta(**changes) -> RuleInput:
    return replace(MARTA, **changes)
