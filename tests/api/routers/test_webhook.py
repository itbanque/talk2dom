import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from talk2dom.api.routers import webhook as webhook_router
from talk2dom.db.models import Base, User


def make_db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def make_app(db_session):
    app = FastAPI()
    app.include_router(webhook_router.router, prefix="/api/v1")

    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    webhook_router.get_db = _get_db_override
    return app


def test_webhook_invalid_payload(monkeypatch):
    app = make_app(make_db_session())
    client = TestClient(app)

    def fake_construct_event(*_args, **_kwargs):
        raise ValueError("bad")

    monkeypatch.setattr(webhook_router.stripe.Webhook, "construct_event", fake_construct_event)

    resp = client.post("/api/v1/stripe", data=b"{}", headers={"stripe-signature": "sig"})
    assert resp.status_code == 400


def test_webhook_payment_intent_updates_credits(monkeypatch):
    db = make_db_session()
    user = User(
        email="u@example.com",
        provider_user_id="local:u",
        one_time_credits=0,
    )
    db.add(user)
    db.commit()

    app = make_app(db)
    client = TestClient(app)

    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"metadata": {"email": "u@example.com", "credit": "5"}}},
    }

    monkeypatch.setattr(webhook_router.stripe.Webhook, "construct_event", lambda *_args, **_kwargs: event)

    resp = client.post("/api/v1/stripe", data=b"{}", headers={"stripe-signature": "sig"})
    assert resp.status_code == 200

    refreshed = db.query(User).filter(User.email == "u@example.com").first()
    assert refreshed.one_time_credits == 5
