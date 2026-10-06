"""Settings from the environment. Sandbox is the only PayPal environment (04_SECURITY.md §2)."""

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_env: str = "sandbox"
    sandbox_buyer_email: str = ""
    merchant_name: str = "Vesper Demo Store"
    merchant_timezone: str = "Asia/Kolkata"
    merchant_currency: str = "USD"
    approval_threshold: Decimal = Decimal("500.00")
    case_ttl_hours: int = 72
    contact_window_start: str = "09:00"
    contact_window_end: str = "20:00"
    kill_switch: bool = False
    demo_mode: bool = True
    demo_fail_strategy: Literal["simulate_event", "internal"] = "internal"
    demo_subscription_amount: Decimal = Decimal("29.00")
    llm_provider: Literal["anthropic", "fixture"] = "anthropic"
    llm_model: str = "claude-opus-5-5"
    llm_api_key: str = ""
    llm_max_calls_per_hour: int = 200
    dashboard_token: str = ""
    database_url: str = "sqlite:///./vesper.db"
    public_api_url: str = ""
    web_origin: str = "http://localhost:3000"
    log_level: str = "info"

    @field_validator("paypal_env")
    @classmethod
    def _sandbox_only(cls, v: str) -> str:
        if v != "sandbox":
            raise ValueError(
                f"PAYPAL_ENV must be 'sandbox' (got {v!r}). Vesper has no live mode; see docs/04_SECURITY.md §2."
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
