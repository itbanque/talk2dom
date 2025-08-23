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
    os.environ.pop("UI_DOMAIN", None)
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

    reset_mail = {"called": False, "to": None, "url": None}

    def fake_send_password_reset_email(to_email: str, reset_url: str):
        reset_mail["called"] = True
        reset_mail["to"] = to_email
        reset_mail["url"] = reset_url

    def fake_confirm_email_token(token: str) -> str:
        if token == "BAD":
            raise Exception("invalid token")
        return token

    monkeypatch.setattr(email_routes, "generate_email_token", fake_generate_email_token)
    monkeypatch.setattr(
        email_routes, "send_verification_email", fake_send_verification_email
    )
    monkeypatch.setattr(
        email_routes, "handle_pending_invites", fake_handle_pending_invites
    )
    monkeypatch.setattr(
        email_routes, "send_password_reset_email", fake_send_password_reset_email
    )
    monkeypatch.setattr(email_routes, "confirm_email_token", fake_confirm_email_token)

    # 将可观察对象挂到 app.state，测试里可取用
    app.state._sent_mail = sent_mail
    app.state._pending_called = pending_called
    app.state._reset_mail = reset_mail

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
        "/api/v1/email/register",
        json={"email": "dup@example.com", "password": "xxxxxxxxx"},
    )
    assert res.status_code == 400
    assert "Email already registered" in res.json()["detail"]


def test_password_length_return_402(client, db_session):
    res = client.post(
        "/api/v1/email/register",
        json={"email": "test@example.com", "password": "xxxxxxx"},
    )
    assert res.status_code == 422
    assert "at least 8 characters" in res.json()["detail"]


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


# -----------
# /email/forgot-password
# -----------
def test_forgot_password_existing_credentials_sends_email(client, app, db_session):
    email = "reset@example.com"
    create_user(db_session, email=email, password="OldPass123!", provider="credentials")
    res = client.post("/api/v1/email/forgot-password", json={"email": email})
    assert res.status_code == 200
    assert res.json()["message"] == "Password reset link sent to your email"

    sent = app.state._reset_mail
    assert sent["called"] is True
    assert sent["to"] == email
    assert sent["url"] == "http://testserver/reset-password?token=TESTTOKEN"


def test_forgot_password_nonexistent_returns_400(client, app):
    res = client.post(
        "/api/v1/email/forgot-password", json={"email": "noone@example.com"}
    )
    assert res.status_code == 400
    assert "Email not registered" in res.json()["detail"]


def test_forgot_password_non_credentials_returns_400(client, app, db_session):
    email = "google@example.com"
    create_user(db_session, email=email, password="x", provider="google")
    res = client.post("/api/v1/email/forgot-password", json={"email": email})
    assert res.status_code == 400
    assert "Email not registered" in res.json()["detail"]


# -----------
# /email/reset-password
# -----------
def test_reset_password_success_changes_password(client, db_session):
    email = "ok@example.com"
    old_pwd = "OldPass123!"
    new_pwd = "NewPass456!"
    create_user(db_session, email=email, password=old_pwd)

    res = client.post(
        "/api/v1/email/reset-password", json={"token": email, "new_password": new_pwd}
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Password reset successfully"

    user = db_session.query(User).filter(User.email == email).first()
    assert hash_helper.verify_password(new_pwd, user.hashed_password)
    assert not hash_helper.verify_password(old_pwd, user.hashed_password)


def test_reset_password_invalid_token_returns_400(client, db_session):
    email = "badtoken@example.com"
    create_user(db_session, email=email, password="Whatever123!")
    res = client.post(
        "/api/v1/email/reset-password",
        json={"token": "BAD", "new_password": "NewPass123!"},
    )
    assert res.status_code == 400
    assert "Invalid or expired token" in res.json()["detail"]


def test_reset_password_non_credentials_returns_400(client, db_session):
    email = "g@example.com"
    create_user(db_session, email=email, password="x", provider="google")
    res = client.post(
        "/api/v1/email/reset-password",
        json={"token": email, "new_password": "NewPass123!"},
    )
    assert res.status_code == 400
    assert "Invalid or expired token" in res.json()["detail"]


def test_reset_password_short_password_returns_422(client, db_session):
    email = "short@example.com"
    create_user(db_session, email=email, password="ShortOld123!")
    res = client.post(
        "/api/v1/email/reset-password", json={"token": email, "new_password": "short"}
    )
    assert res.status_code == 422
    assert "at least 8 characters" in res.json()["detail"]
