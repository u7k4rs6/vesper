"""Payer country → (timezone, locale) for customers PayPal tells us about. UTC/en-US fallback."""

TZ_BY_COUNTRY: dict[str, tuple[str, str]] = {
    "US": ("America/Chicago", "en-US"),
    "CA": ("America/Toronto", "en-CA"),
    "MX": ("America/Mexico_City", "es-MX"),
    "BR": ("America/Sao_Paulo", "pt-BR"),
    "AR": ("America/Argentina/Buenos_Aires", "es-AR"),
    "CO": ("America/Bogota", "es-CO"),
    "GB": ("Europe/London", "en-GB"),
    "IE": ("Europe/Dublin", "en-IE"),
    "ES": ("Europe/Madrid", "es-ES"),
    "FR": ("Europe/Paris", "fr-FR"),
    "DE": ("Europe/Berlin", "de-DE"),
    "IT": ("Europe/Rome", "it-IT"),
    "NL": ("Europe/Amsterdam", "nl-NL"),
    "IN": ("Asia/Kolkata", "hi-IN"),
    "SG": ("Asia/Singapore", "en-SG"),
    "JP": ("Asia/Tokyo", "ja-JP"),
    "CN": ("Asia/Shanghai", "zh-CN"),
    "AU": ("Australia/Sydney", "en-AU"),
    "NZ": ("Pacific/Auckland", "en-NZ"),
}


def tz_and_locale(country_code: str | None) -> tuple[str, str]:
    return TZ_BY_COUNTRY.get((country_code or "").upper(), ("UTC", "en-US"))
