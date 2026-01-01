import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from talk2dom.db.models import Base, User


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    return TestingSessionLocal()


def test_get_or_create_google_user_creates_new(monkeypatch):
    db = make_session()

    sent = {"called": False}

    def fake_send(email):
        sent["called"] = True
        sent["email"] = email

    monkeypatch.setattr("talk2dom.db.models.send_welcome_email", fake_send)

    user_info = {"email": "a@example.com", "name": "A", "sub": "1"}
    user = asyncio.run(User.get_or_create_google_user(db, user_info))

    assert user.email == "a@example.com"
    assert user.provider == "google"
    assert sent["called"] is True


def test_get_or_create_google_user_updates_existing(monkeypatch):
    db = make_session()
    existing = User(
        email="a@example.com",
        provider_user_id="old",
        name="Old",
        provider="google",
    )
    db.add(existing)
    db.commit()

    monkeypatch.setattr("talk2dom.db.models.send_welcome_email", lambda *_: None)

    user_info = {"email": "a@example.com", "name": "New", "sub": "2"}
    user = asyncio.run(User.get_or_create_google_user(db, user_info))

    assert user.provider_user_id == "2"
    assert user.name == "New"


def test_get_or_create_github_user_requires_email(monkeypatch):
    db = make_session()
    monkeypatch.setattr("talk2dom.db.models.send_welcome_email", lambda *_: None)

    user_info = {"id": 1, "login": "octo", "name": "Octo"}
    try:
        asyncio.run(User.get_or_create_github_user(db, user_info, email=None))
    except ValueError as exc:
        assert "GitHub email" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_get_or_create_github_user_existing_by_provider(monkeypatch):
    db = make_session()
    monkeypatch.setattr("talk2dom.db.models.send_welcome_email", lambda *_: None)

    existing = User(
        email="old@example.com",
        provider_user_id="123",
        name="Old",
        provider="github",
    )
    db.add(existing)
    db.commit()

    user_info = {"id": 123, "login": "octo", "name": "Octo"}
    user = asyncio.run(
        User.get_or_create_github_user(db, user_info, email="new@example.com")
    )

    assert user.email == "new@example.com"
    assert user.provider == "github"
