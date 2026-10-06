"""Slot-based messages (§6.6). The model writes a template; code fills every number and name."""

import re
import string
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from babel.dates import format_date
from babel.numbers import format_currency
from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

PLACEHOLDERS = frozenset({"first_name", "merchant", "description", "amount", "due_date"})
MAX_LENGTH = 400
INVOICE_DUE_DAYS = 7

# Checked in every language regardless of locale; a promise is a promise in any language.
BANNED_PHRASES: dict[str, tuple[str, ...]] = {
    "en": (
        "discount", "refund", "guarantee", "urgent", "final notice", "last chance", "act now",
        "coupon", "promo", "free", "penalty", "legal action", "collections", "overdue", "deadline",
    ),
    "es": (
        "descuento", "reembolso", "garantía", "garantia", "urgente", "último aviso", "ultimo aviso",
        "última oportunidad", "ultima oportunidad", "cupón", "cupon", "gratis", "acción legal",
    ),
    "hi": ("छूट", "रिफंड", "गारंटी", "तुरंत", "अंतिम सूचना", "मुफ्त", "कानूनी कार्रवाई"),
}

_LINK = re.compile(r"(https?:|www\.|://|\.com\b|\.[a-z]{2,}/)", re.IGNORECASE)

FALLBACKS: dict[str, str] = {
    "en": (
        "Hi {first_name}, your payment of {amount} for {description} did not go through. "
        "If you would still like it, you can pay with this PayPal invoice by {due_date}. "
        "Thank you, {merchant}"
    ),
    "es": (
        "Hola {first_name}, no pudimos completar tu pago de {amount} por {description}. "
        "Si aún lo quieres, puedes pagar con esta factura de PayPal hasta el {due_date}. "
        "Gracias, {merchant}"
    ),
    "hi": (
        "नमस्ते {first_name}, {description} के लिए आपका {amount} का भुगतान पूरा नहीं हो सका। "
        "अगर आप अब भी इसे लेना चाहते हैं, तो {due_date} तक इस PayPal इनवॉइस से भुगतान कर सकते हैं। "
        "धन्यवाद, {merchant}"
    ),
}


@dataclass
class Validation:
    ok: bool
    problems: list[str] = field(default_factory=list)


def language_of(locale: str) -> str:
    return locale.replace("_", "-").split("-")[0].lower()


def _placeholders(template: str) -> list[str] | None:
    try:
        return [name for _, name, _, _ in string.Formatter().parse(template) if name is not None]
    except ValueError:
        return None


def validate(template: str, locale: str) -> Validation:
    problems: list[str] = []
    names = _placeholders(template)
    if names is None:
        problems.append("Malformed placeholder braces.")
    else:
        unknown = sorted({n for n in names if n not in PLACEHOLDERS})
        if unknown:
            problems.append(f"Unapproved placeholders: {', '.join(unknown)}.")
    if any(ch.isdigit() for ch in template):
        problems.append("Contains digits.")
    if _LINK.search(template):
        problems.append("Contains a link.")
    lowered = template.casefold()
    hits = sorted({p for phrases in BANNED_PHRASES.values() for p in phrases if _contains_phrase(lowered, p)})
    if hits:
        problems.append(f"Banned phrases: {', '.join(hits)}.")
    if len(template) > MAX_LENGTH:
        problems.append(f"Longer than {MAX_LENGTH} characters.")
    detected = _detect_language(template)
    if detected != language_of(locale):
        problems.append(f"Language is {detected or 'unknown'}, expected {language_of(locale)}.")
    return Validation(ok=not problems, problems=problems)


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = phrase.casefold()
    if phrase.isascii():
        return re.search(rf"\b{re.escape(phrase)}\b", text) is not None
    return phrase in text


def _detect_language(template: str) -> str | None:
    prose = re.sub(r"\{[^}]*\}", " ", template)
    prose = prose.replace("PayPal", " ")
    try:
        return detect(prose)
    except LangDetectException:
        return None


def fallback(locale: str) -> tuple[str, str]:
    """Return (template, language). English for anything without its own template."""
    lang = language_of(locale)
    if lang in FALLBACKS:
        return FALLBACKS[lang], lang
    return FALLBACKS["en"], "en"


def due_date(today: date) -> date:
    return today + timedelta(days=INVOICE_DUE_DAYS)


def render(
    template: str,
    *,
    first_name: str,
    merchant: str,
    description: str,
    amount: Decimal,
    currency: str,
    locale: str,
    due: date,
) -> str:
    babel_locale = locale.replace("-", "_")
    return template.format(
        first_name=first_name,
        merchant=merchant,
        description=description,
        amount=format_currency(amount, currency, locale=babel_locale),
        due_date=format_date(due, format="long", locale=babel_locale),
    )
