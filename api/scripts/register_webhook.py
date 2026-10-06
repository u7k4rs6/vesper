"""Point PayPal's sandbox webhook at PUBLIC_API_URL.

With PAYPAL_WEBHOOK_ID already set, the existing webhook is updated in place, so the id (and .env)
stays the same when a tunnel URL changes. Otherwise a new webhook is registered and its id printed.
"""

import sys

from vesper.config import get_settings
from vesper.paypal.client import PayPalError, get_client
from vesper.paypal.webhooks import EVENT_TYPES


def main() -> int:
    settings = get_settings()
    if not (settings.paypal_client_id and settings.paypal_client_secret and settings.public_api_url):
        print("Set PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET and PUBLIC_API_URL in api/.env first.", file=sys.stderr)
        return 1
    url = settings.public_api_url.rstrip("/") + "/webhooks/paypal"
    event_types = [{"name": name} for name in EVENT_TYPES]
    client = get_client()

    if settings.paypal_webhook_id:
        try:
            client.request(
                "PATCH",
                f"/v1/notifications/webhooks/{settings.paypal_webhook_id}",
                json=[
                    {"op": "replace", "path": "/url", "value": url},
                    {"op": "replace", "path": "/event_types", "value": event_types},
                ],
            )
            print(f"Updated webhook {settings.paypal_webhook_id} to {url}. Nothing to change in .env.")
            return 0
        except PayPalError as e:
            if e.status != 404:
                print(f"PayPal refused the update: {e.status} {e.body}", file=sys.stderr)
                return 1
            print("PAYPAL_WEBHOOK_ID no longer exists at PayPal; registering a new webhook.")

    try:
        body = client.request("POST", "/v1/notifications/webhooks", json={"url": url, "event_types": event_types})
    except PayPalError as e:
        print(f"PayPal refused the registration: {e.status} {e.body}", file=sys.stderr)
        return 1
    print(f"Registered {url}")
    print(f"PAYPAL_WEBHOOK_ID={body['id']}   <- put this in api/.env and restart the API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
