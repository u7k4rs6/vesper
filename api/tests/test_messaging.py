from datetime import date
from decimal import Decimal

import pytest

from vesper.pipeline import messaging
from vesper.pipeline.messaging import FALLBACKS, fallback, render, validate

GOOD_EN = (
    "Hi {first_name}, your payment of {amount} for {description} did not go through. "
    "If you still want it, you can pay with this invoice by {due_date}. Thanks, {merchant}"
)


def test_good_template_passes():
    assert validate(GOOD_EN, "en-US").ok


@pytest.mark.parametrize(
    "template",
    [
        GOOD_EN + " Pay within 24 hours.",  # digit
        GOOD_EN + " Visit https://example.com",  # link
        GOOD_EN + " Visit www.example.com",  # link
        GOOD_EN + " We can offer a discount.",  # banned
        GOOD_EN + " This is your final notice.",  # banned
        GOOD_EN + " We guarantee it works.",  # banned (guarantee as a word)
    ],
)
def test_message_validate_rejects_digits_links_and_banned_phrases(template):
    assert not validate(template, "en-US").ok


def test_unicode_digits_are_rejected():
    assert not validate(GOOD_EN.replace("Thanks", "Thanks ٣"), "en-US").ok


def test_unapproved_placeholder_rejected():
    result = validate(GOOD_EN + " {payer_link}", "en-US")
    assert not result.ok and any("payer_link" in p for p in result.problems)


def test_attribute_access_placeholder_rejected():
    assert not validate("Hi {first_name.__class__}, " + GOOD_EN, "en-US").ok


def test_malformed_braces_rejected():
    assert not validate(GOOD_EN + " {", "en-US").ok


def test_too_long_rejected():
    assert not validate(GOOD_EN + " Thanks again." * 30, "en-US").ok


def test_language_mismatch_rejected():
    assert not validate(GOOD_EN, "es-ES").ok


def test_banned_phrases_checked_in_every_language():
    spanish = "Hola {first_name}, tenemos un descuento para ti en {description}. Gracias, {merchant}"
    assert not validate(spanish, "es-ES").ok


@pytest.mark.parametrize("lang", sorted(FALLBACKS))
def test_fallback_templates_pass_validation(lang):
    template, language = fallback(lang)
    assert language == lang
    assert validate(template, lang).ok


def test_unknown_locale_falls_back_to_english():
    template, language = fallback("fr-FR")
    assert language == "en" and template == FALLBACKS["en"]


def test_render_inserts_amount_and_date_per_locale():
    template, _ = fallback("es-ES")
    text = render(
        template,
        first_name="Marta",
        merchant="Vesper Demo Store",
        description="Linen Throw",
        amount=Decimal("89.00"),
        currency="USD",
        locale="es-ES",
        due=date(2026, 10, 12),
    )
    assert "89,00" in text and "12 de octubre de 2026" in text and "Marta" in text


def test_due_date_is_seven_days_out():
    assert messaging.due_date(date(2026, 10, 5)) == date(2026, 10, 12)
