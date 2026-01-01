from fastapi import FastAPI
from fastapi.testclient import TestClient

from talk2dom.api.routers import status as status_router


def test_healthz_ok():
    app = FastAPI()
    app.include_router(status_router.router, prefix="/api/v1")
    client = TestClient(app)

    resp = client.get("/api/v1/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
