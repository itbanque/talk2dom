from fastapi import FastAPI
from fastapi.testclient import TestClient

from talk2dom.api.routers import subscription as subscription_router
from talk2dom.db.models import User


def make_app():
    app = FastAPI()
    app.include_router(subscription_router.router, prefix="/api/v1")

    def fake_db():
        yield None

    def fake_user():
        return User(
            email="u@example.com",
            provider_user_id="local:u",
            id="123",
            stripe_subscription_id="sub",
            stripe_customer_id="cust",
        )

    app.dependency_overrides[subscription_router.get_current_user] = fake_user
    app.dependency_overrides[subscription_router.get_db] = fake_db
    return app


def test_start_subscription_free_plan():
    app = make_app()
    client = TestClient(app)

    resp = client.post("/api/v1/create-subscription", params={"plan": "free"})
    assert resp.status_code == 200
    assert "Free plan" in resp.json()["message"]


def test_start_subscription_creates_checkout(monkeypatch):
    app = make_app()
    client = TestClient(app)

    monkeypatch.setattr(subscription_router, "create_checkout_session", lambda *_args, **_kwargs: "http://checkout")

    resp = client.post("/api/v1/create-subscription", params={"plan": "pro"})
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "http://checkout"


def test_start_one_time_creates_checkout(monkeypatch):
    app = make_app()
    client = TestClient(app)

    monkeypatch.setattr(subscription_router, "create_checkout_session", lambda *_args, **_kwargs: "http://checkout")

    resp = client.post("/api/v1/create-one-time", params={"plan": "10"})
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "http://checkout"


def test_subscription_success_page():
    app = make_app()
    client = TestClient(app)

    resp = client.get("/api/v1/success", params={"session_id": "sess"})
    assert resp.status_code == 200
    assert "Subscription Successful" in resp.text


def test_subscription_cancel_page():
    app = make_app()
    client = TestClient(app)

    resp = client.get("/api/v1/cancel")
    assert resp.status_code == 200
    assert "Subscription canceled" in resp.text


def test_cancel_subscription_success(monkeypatch):
    app = make_app()
    client = TestClient(app)

    monkeypatch.setattr(subscription_router.stripe.Subscription, "modify", lambda *_args, **_kwargs: None)

    resp = client.post("/api/v1/cancel")
    assert resp.status_code == 200
    assert resp.json()["detail"].startswith("Subscription cancelled")


def test_billing_history_empty(monkeypatch):
    app = make_app()
    client = TestClient(app)

    class DummyInvoices:
        def auto_paging_iter(self):
            return iter([])

    monkeypatch.setattr(subscription_router.stripe.Invoice, "list", lambda *_args, **_kwargs: DummyInvoices())

    resp = client.get("/api/v1/history")
    assert resp.status_code == 200
    assert resp.json() == []
