import pytest

from talk2dom.api import stripe_service


def test_create_checkout_session_invalid_plan(monkeypatch):
    monkeypatch.setattr(stripe_service, "PRICE_IDS", {"free": None})
    with pytest.raises(Exception):
        stripe_service.create_checkout_session("u@example.com", "free")


def test_create_checkout_session_subscription(monkeypatch):
    monkeypatch.setattr(stripe_service, "PRICE_IDS", {"pro": "price"})

    class DummySession:
        url = "http://checkout"

    def fake_create(**_kwargs):
        return DummySession()

    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", fake_create)

    url = stripe_service.create_checkout_session("u@example.com", "pro", mode="subscription")
    assert url == "http://checkout"


def test_create_checkout_session_payment(monkeypatch):
    monkeypatch.setattr(stripe_service, "PRICE_IDS", {"10": "price"})

    class DummySession:
        url = "http://checkout"

    def fake_create(**_kwargs):
        return DummySession()

    monkeypatch.setattr(stripe_service.stripe.checkout.Session, "create", fake_create)

    url = stripe_service.create_checkout_session("u@example.com", "10", mode="payment")
    assert url == "http://checkout"
