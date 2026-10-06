"""Thin httpx client for PayPal. Sandbox only; there is no other base URL in this codebase."""

import time
from typing import Any

import httpx

from vesper.config import get_settings

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
TIMEOUT = httpx.Timeout(15.0)


class PayPalError(Exception):
    def __init__(self, status: int, body: dict[str, Any]):
        self.status = status
        self.body = body
        super().__init__(f"PayPal {status}: {body.get('name') or body.get('error')}")

    @property
    def issues(self) -> list[str]:
        return [d.get("issue", "") for d in self.body.get("details", []) if isinstance(d, dict)]


class PayPalClient:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        settings = get_settings()
        self._client_id = settings.paypal_client_id
        self._secret = settings.paypal_client_secret
        self._http = httpx.Client(base_url=SANDBOX_BASE, timeout=TIMEOUT, transport=transport)
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        if not (self._client_id and self._secret):
            raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are not set.")
        r = self._http.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._secret),
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._token_expires_at = time.monotonic() + int(body.get("expires_in", 0)) - 60
        return self._token

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        content: bytes | None = None,
        request_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        h = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if request_id:
            h["PayPal-Request-Id"] = request_id
        if headers:
            h.update(headers)
        r = self._http.request(method, path, json=json, content=content, headers=h)
        body = r.json() if r.content else {}
        if r.status_code >= 400:
            raise PayPalError(r.status_code, body)
        return body


_client: PayPalClient | None = None


def get_client() -> PayPalClient:
    global _client
    if _client is None:
        _client = PayPalClient()
    return _client
