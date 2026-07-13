import os
import re
import uuid

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["UI_DOMAIN"] = "http://ui.example"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from talk2dom.api.main import app
from talk2dom.api.routers.admin import require_admin
from talk2dom.db.models import Base, User
from talk2dom.api.deps import get_db

ADMIN_TOKEN = "test-admin-token"


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        provider_user_id="admin-test-provider-id",
        email="member@example.com",
        name="Member",
        plan="free",
        subscription_credits=100,
        one_time_credits=0,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # https base_url so the Secure session cookie is stored and sent
    with TestClient(app, base_url="https://testserver") as c:
        yield c
    app.dependency_overrides = {}


def login(client):
    resp = client.post(
        "/admin/login", data={"token": ADMIN_TOKEN}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/"


def test_admin_requires_login(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"


def test_login_with_wrong_token(client):
    resp = client.post("/admin/login", data={"token": "nope"})
    assert resp.status_code == 401
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 303


def test_login_disabled_without_env(client, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN")
    resp = client.post("/admin/login", data={"token": ADMIN_TOKEN})
    assert resp.status_code == 401
    resp = client.get("/admin/login")
    assert "Token login is disabled" in resp.text


def test_token_session_dies_when_env_removed(client, monkeypatch):
    login(client)
    monkeypatch.delenv("ADMIN_TOKEN")
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/login"


def test_user_list(client, test_user):
    login(client)
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert test_user.email in resp.text

    resp = client.get("/admin/", params={"q": "no-such-user"})
    assert test_user.email not in resp.text

    resp = client.get("/admin/", params={"plan": "pro"})
    assert test_user.email not in resp.text


def test_update_user_plan_and_credits(client, db_session, test_user):
    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    assert page.status_code == 200
    csrf = re.search(r'name="csrf_token" value="([0-9a-f]+)"', page.text).group(1)

    resp = client.post(
        f"/admin/users/{test_user.id}",
        data={
            "csrf_token": csrf,
            "plan": "pro",
            "subscription_credits": 5000,
            "one_time_credits": 42,
            "is_active": "on",
            "is_admin": "on",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db_session.refresh(test_user)
    assert test_user.plan == "pro"
    assert test_user.subscription_credits == 5000
    assert test_user.one_time_credits == 42
    assert test_user.is_active is True
    assert test_user.is_admin is True


def test_update_rejects_bad_csrf(client, db_session, test_user):
    login(client)
    client.get(f"/admin/users/{test_user.id}")  # seeds a csrf token in session
    resp = client.post(
        f"/admin/users/{test_user.id}",
        data={
            "csrf_token": "f" * 32,
            "plan": "pro",
            "subscription_credits": 1,
            "one_time_credits": 1,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 403
    db_session.refresh(test_user)
    assert test_user.plan == "free"


def test_update_rejects_invalid_plan(client, db_session, test_user):
    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    csrf = re.search(r'name="csrf_token" value="([0-9a-f]+)"', page.text).group(1)
    resp = client.post(
        f"/admin/users/{test_user.id}",
        data={
            "csrf_token": csrf,
            "plan": "platinum",
            "subscription_credits": 1,
            "one_time_credits": 1,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    db_session.refresh(test_user)
    assert test_user.plan == "free"


def _session_request(session: dict) -> Request:
    return Request({"type": "http", "session": session, "headers": []})


def test_require_admin_with_admin_session_user(db_session, test_user):
    test_user.is_admin = True
    db_session.commit()
    actor = require_admin(
        _session_request({"user": {"id": str(test_user.id)}}), db_session
    )
    assert actor == test_user.email


def test_require_admin_rejects_regular_session_user(db_session, test_user):
    with pytest.raises(HTTPException) as exc:
        require_admin(_session_request({"user": {"id": str(test_user.id)}}), db_session)
    assert exc.value.status_code == 303
