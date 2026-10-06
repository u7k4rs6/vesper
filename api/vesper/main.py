import asyncio
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from vesper.config import get_settings
from vesper.limits import limiter
from vesper.routes import dashboard, store, webhooks
from vesper.scheduler import run_forever

settings = get_settings()  # aborts startup unless PAYPAL_ENV=sandbox

structlog.configure(
    processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_forever())
    yield
    task.cancel()


app = FastAPI(title="Vesper", docs_url=None, redoc_url=None, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware, allow_origins=[settings.web_origin], allow_methods=["GET", "POST"], allow_headers=["*"]
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(StarletteHTTPException)
async def _http_error(request: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail).replace(" ", "_").lower(), str(exc.detail))


@app.exception_handler(RateLimitExceeded)
async def _rate_limited(request: Request, exc: RateLimitExceeded):
    return _error(429, "rate_limited", "Try again in a minute.")


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    structlog.get_logger().exception("unhandled", path=request.url.path)
    return _error(500, "internal", "Something went wrong.")


@app.get("/api/health")
def health():
    return {"ok": True, "env": "sandbox", "kill_switch": settings.kill_switch, "demo_mode": settings.demo_mode}


app.include_router(webhooks.router)
app.include_router(dashboard.router)
if settings.demo_mode:
    app.include_router(store.router)
