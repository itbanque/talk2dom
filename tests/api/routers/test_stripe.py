from fastapi import FastAPI
from fastapi.testclient import TestClient

from talk2dom.api.routers import stripe as stripe_router
from talk2dom.db.models import User


def make_app(monkeypatch):
    app = FastAPI()
    app.include_router(stripe_router.router, prefix="/api/v1")

    def fake_user():
        return User(email="u@example.com", provider_user_id="local:u", id="123")

    app.dependency_overrides[stripe_router.get_current_user] = fake_user

    return app


def test_create_payment_intent_success(monkeypatch):
    app = make_app(monkeypatch)
    client = TestClient(app)

    monkeypatch.setattr(
        stripe_router, "CREDIT_PRICE_MAPPING", {"1000": "1000"}
    )

    class DummyIntent:
        client_secret = "secret"

    def fake_create(**kwargs):
        return DummyIntent()

    monkeypatch.setattr(stripe_router.stripe.PaymentIntent, "create", fake_create)

    resp = client.post("/api/v1/create-payment-intent", json={"number_of_credit": 1000})
    assert resp.status_code == 200
    assert resp.json()["clientSecret"] == "secret"


def test_create_subscription_invalid_plan(monkeypatch):
    app = make_app(monkeypatch)
    client = TestClient(app)

    monkeypatch.setattr(stripe_router, "PLAN_PRICE_MAPPING", {"pro": "price"})

    resp = client.post("/api/v1/create-subscription", params={"plan": "bad"})
    assert resp.status_code == 400


def test_create_subscription_success(monkeypatch):
    app = make_app(monkeypatch)
    client = TestClient(app)

    monkeypatch.setattr(stripe_router, "PLAN_PRICE_MAPPING", {"pro": "price"})

    class DummyList:
        data = []

    class DummySubscription(dict):
        id = "sub"

    def fake_customer_list(**_kwargs):
        return DummyList()

    def fake_customer_create(**_kwargs):
        return type("C", (), {"id": "cust"})()

    def fake_subscription_create(**_kwargs):
        return DummySubscription({
            "id": "sub",
            "latest_invoice": {"payments": {"data": [{"payment": {"payment_intent": "pi"}}]}},
        })

    def fake_payment_intent_retrieve(_):
        return {"client_secret": "secret"}

    monkeypatch.setattr(stripe_router.stripe.Customer, "list", fake_customer_list)
    monkeypatch.setattr(stripe_router.stripe.Customer, "create", fake_customer_create)
    monkeypatch.setattr(stripe_router.stripe.Subscription, "create", fake_subscription_create)
    monkeypatch.setattr(stripe_router.stripe.PaymentIntent, "retrieve", fake_payment_intent_retrieve)

    resp = client.post("/api/v1/create-subscription", params={"plan": "pro"})
    assert resp.status_code == 200
    assert resp.json()["clientSecret"] == "secret"


def test_update_subscription_success(monkeypatch):
    app = make_app(monkeypatch)
    client = TestClient(app)

    monkeypatch.setattr(stripe_router, "PLAN_PRICE_MAPPING", {"pro": "price"})

    def fake_retrieve(_):
        return {"id": "sub", "items": {"data": [{"id": "item"}]}}

    def fake_modify_item(*_args, **_kwargs):
        return {"id": "new-item"}

    def fake_modify_sub(*_args, **_kwargs):
        return None

    monkeypatch.setattr(stripe_router.stripe.Subscription, "retrieve", fake_retrieve)
    monkeypatch.setattr(stripe_router.stripe.SubscriptionItem, "modify", fake_modify_item)
    monkeypatch.setattr(stripe_router.stripe.Subscription, "modify", fake_modify_sub)

    # Attach subscription id to user via override
    def fake_user():
        return User(
            email="u@example.com",
            provider_user_id="local:u",
            id="123",
            stripe_subscription_id="sub",
        )

    app.dependency_overrides[stripe_router.get_current_user] = fake_user

    resp = client.post("/api/v1/update-subscription", params={"plan": "pro"})
    assert resp.status_code == 200
    assert resp.json()["subscriptionId"] == "sub"
