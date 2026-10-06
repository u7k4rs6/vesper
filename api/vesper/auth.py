import hmac

from fastapi import Header, HTTPException

from vesper.config import get_settings


def require_dashboard_token(x_dashboard_token: str = Header(default="")) -> None:
    expected = get_settings().dashboard_token
    if not expected or not hmac.compare_digest(x_dashboard_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="unauthorised")
