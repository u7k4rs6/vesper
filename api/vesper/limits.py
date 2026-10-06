from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def client_key(request: Request) -> str:
    # Behind the web proxy every call comes from one address, so the proxy forwards the browser's.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or get_remote_address(request)


def global_key(request: Request | None = None) -> str:
    return "global"


limiter = Limiter(key_func=client_key)
