from fastapi import FastAPI
from fastapi.testclient import TestClient

from talk2dom.api.routers import sentry as sentry_router


def test_sentry_debug_raises():
    app = FastAPI()
    app.include_router(sentry_router.router, prefix="/api/v1")
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/api/v1/debug")
    assert resp.status_code == 500
