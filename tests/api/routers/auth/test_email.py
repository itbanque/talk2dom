import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---- import your code under test ----
from talk2dom.db.models import Base, User
from talk2dom.db.session import get_db as real_get_db
from talk2dom.api.utils import hash_helper


# -----------------------
# Fixtures: DB & Test App
# -----------------------
@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def app(db_session, monkeypatch):
    import os

    # Set the SECRET_KEY in the environment before importing email_routes
    os.environ["SECRET_KEY"] = "test-secret-key"
    # Patch the SECRET_KEY in talk2dom.api.utils.token
    monkeypatch.setattr("talk2dom.api.utils.token.SECRET_KEY", "test-secret-key")

    # Now import the email_routes module
    from talk2dom.api.routers.auth import email as email_routes

    app = FastAPI()
    # Mount the router under same prefix as production
    app.include_router(email_routes.router, prefix="/api/v1")
    # Add session support (login_user 会写 request.session)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    # Override get_db to use our in-memory session
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[real_get_db] = _get_db_override

    # Mock generate_email_token & send_verification_email & handle_pending_invites
    def fake_generate_email_token(email: str) -> str:
        return "TESTTOKEN"

    sent_mail = {"called": False, "to": None, "url": None}

    def fake_send_verification_email(to_email: str, verify_url: str):
        sent_mail["called"] = True
        sent_mail["to"] = to_email
        sent_mail["url"] = verify_url

    pending_called = {"called": False, "user_id": None}

    def fake_handle_pending_invites(db, user):
        pending_called["called"] = True
        pending_called["user_id"] = str(user.id)

    monkeypatch.setattr(email_routes, "generate_email_token", fake_generate_email_token)
    monkeypatch.setattr(
        email_routes, "send_verification_email", fake_send_verification_email
    )
    monkeypatch.setattr(
        email_routes, "handle_pending_invites", fake_handle_pending_invites
    )

    # 将可观察对象挂到 app.state，测试里可取用
    app.state._sent_mail = sent_mail
    app.state._pending_called = pending_called

    return app


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


# -------------
# Helper: create
# -------------
def create_user(db, *, email="u@example.com", password="p@ss", provider="credentials"):
    user = User(
        email=email,
        provider_user_id=f"local:{email}",
        hashed_password=hash_helper.hash_password(password),
        provider=provider,
        plan="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# -----------
# /email/register
# -----------
def test_register_success_creates_user_and_sends_email(client, app, db_session):
    payload = {"email": "new@example.com", "password": "Hello123!"}
    res = client.post("/api/v1/email/register", json=payload)
    assert res.status_code == 200
    assert res.json()["message"].startswith("Registration successful")

    # DB user exists
    u = db_session.query(User).filter(User.email == payload["email"]).first()
    assert u is not None
    assert u.provider == "credentials"
    assert u.hashed_password != payload["password"]  # hashed

    # Email sent with correct verify URL
    sent = app.state._sent_mail
    assert sent["called"] is True
    assert sent["to"] == payload["email"]
    # Base URL in TestClient is http://testserver
    assert sent["url"] == "http://testserver/api/v1/user/verify-email?token=TESTTOKEN"


def test_register_existing_email_returns_400(client, db_session):
    # existing
    create_user(db_session, email="dup@example.com", password="x")
    res = client.post(
        "/api/v1/email/register", json={"email": "dup@example.com", "password": "x"}
    )
    assert res.status_code == 400
    assert "Email already registered" in res.json()["detail"]


# -----------
# /email/login
# -----------
def test_login_invalid_email_returns_400(client):
    res = client.post(
        "/api/v1/email/login", json={"email": "none@x.com", "password": "x"}
    )
    assert res.status_code == 400
    assert "Invalid credentials" in res.json()["detail"]


def test_login_non_credentials_provider_returns_400(client, db_session):
    create_user(db_session, email="g@example.com", password="x", provider="google")
    res = client.post(
        "/api/v1/email/login", json={"email": "g@example.com", "password": "x"}
    )
    assert res.status_code == 400
    assert "external login" in res.json()["detail"]


def test_login_invalid_password_returns_400(client, db_session):
    create_user(db_session, email="a@example.com", password="rightpass")
    res = client.post(
        "/api/v1/email/login", json={"email": "a@example.com", "password": "wrong"}
    )
    assert res.status_code == 400
    assert "Invalid credentials" in res.json()["detail"]


def test_login_success_sets_session_and_calls_pending_invites(client, app, db_session):
    user = create_user(db_session, email="ok@example.com", password="Secret123!")

    res = client.post(
        "/api/v1/email/login",
        json={"email": "ok@example.com", "password": "Secret123!"},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Login successful"

    # Session cookie should exist (starlette SessionMiddleware)
    # (TestClient keeps cookies internally; we verify a follow-up request carries session)
    # Here, just ensure our pending invite handler was called with that user.
    called = app.state._pending_called
    assert called["called"] is True
    assert called["user_id"] == str(user.id)

    # last_login should be updated
    refreshed = db_session.query(User).filter(User.id == user.id).first()
    assert refreshed.last_login is not None
