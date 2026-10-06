import typing
from decimal import Decimal

import pytest
from pydantic import ValidationError

from vesper.pipeline.schemas import Diagnosis, Proposal

NUMERIC = (int, float, Decimal, complex)


def _types(annotation):
    args = typing.get_args(annotation)
    if not args:
        yield annotation
    for arg in args:
        yield from _types(arg)


def test_output_schemas_have_no_numeric_fields():
    for model in (Diagnosis, Proposal):
        for name, field in model.model_fields.items():
            for t in _types(field.annotation):
                # Either a type (str, NoneType) or a Literal value; neither may be numeric.
                assert not (isinstance(t, type) and issubclass(t, NUMERIC)), f"{model.__name__}.{name}"
                assert not isinstance(t, NUMERIC), f"{model.__name__}.{name}"


def test_proposal_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Proposal.model_validate(
            {"action": "SEND_INVOICE", "rationale": "x", "language": "es", "amount": 10}
        )


def test_diagnosis_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Diagnosis.model_validate(
            {"category": "soft", "cause": "x", "customer_context": "y", "confidence": "high", "score": 0.9}
        )


def test_proposal_rejects_actions_outside_the_menu():
    with pytest.raises(ValidationError):
        Proposal.model_validate({"action": "REFUND", "rationale": "x", "language": "en"})


def test_confidence_is_categorical():
    with pytest.raises(ValidationError):
        Diagnosis.model_validate({"category": "soft", "cause": "x", "customer_context": "y", "confidence": 0.9})


@pytest.mark.parametrize("language", ["english", "EN", "es_ES", "es-es", ""])
def test_proposal_rejects_bad_language_codes(language):
    with pytest.raises(ValidationError):
        Proposal.model_validate({"action": "WAIT", "rationale": "x", "language": language})


def test_message_template_length_capped():
    with pytest.raises(ValidationError):
        Proposal.model_validate({"action": "SEND_INVOICE", "rationale": "x", "language": "en", "message_template": "a" * 401})
