import os

os.environ.setdefault("LLM_PROVIDER", "fixture")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["PAYPAL_ENV"] = "sandbox"
os.environ["PAYPAL_CLIENT_ID"] = "test-client"
os.environ["PAYPAL_CLIENT_SECRET"] = "test-secret"
os.environ["PAYPAL_WEBHOOK_ID"] = "WH-TEST"
os.environ["SANDBOX_BUYER_EMAIL"] = "buyer@example.com"
os.environ["DASHBOARD_TOKEN"] = "test-token"
os.environ["DEMO_MODE"] = "true"

import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from vesper.db import Base, get_session  # noqa: E402
from vesper.paypal import client as paypal_client  # noqa: E402

SANDBOX = "https://api-m.sandbox.paypal.com"


@pytest.fixture
def session_factory():
    # TEST_DATABASE_URL=postgresql+psycopg://... runs the suite against Postgres, as deployed.
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        engine = create_engine(url)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    if url:
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture
def paypal():
    paypal_client._client = None
    with respx.mock(base_url=SANDBOX, assert_all_called=False) as mock:
        mock.post("/v1/oauth2/token").respond(200, json={"access_token": "tok", "expires_in": 3600})
        yield mock
    paypal_client._client = None


@pytest.fixture
def api(session_factory, paypal):
    from vesper.limits import limiter
    from vesper.main import app

    limiter.reset()

    def override():
        with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def llm():
    from vesper.llm import provider

    provider._provider = provider.FixtureProvider()
    provider.budget._calls.clear()
    yield provider._provider
    provider._provider = None
