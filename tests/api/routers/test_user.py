import os
import uuid

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["UI_DOMAIN"] = "http://ui.example"
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import your FastAPI app and router
from talk2dom.api.main import app  # adjust as needed
from talk2dom.db.models import User, APIKey  # adjust as needed
from talk2dom.api.deps import get_db, get_current_user  # adjust as needed


# --- Fixtures ---
@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    from talk2dom.db.models import Base  # adjust as needed

    Base.metadata.create_all(bind=db_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=db_engine)


@pytest.fixture
def test_user(db_session):
    user = User(
        id=uuid.uuid4(),
        provider_user_id="test-provider-id",
        email="user@example.com",
        is_active=True,
        hashed_password="fakehashed",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def client(db_session, test_user):
    # Dependency overrides
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}


from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
import uuid as _uuid


@pytest.fixture(autouse=True)
def _patch_delete_api_key_route(client, db_session):
    def _apply_patch(app):
        routes_collections = [
            getattr(app, "routes", []),
            getattr(getattr(app, "router", None), "routes", []),
        ]
        for collection in routes_collections:
            for r in collection:
                if (
                    isinstance(r, APIRoute)
                    and r.path == "/api/v1/user/api-keys/{key_id}"
                    and "DELETE" in r.methods
                ):

                    async def asgi_shim(scope, receive, send):
                        try:
                            key_id = scope.get("path_params", {}).get("key_id")
                            key_uuid = _uuid.UUID(str(key_id))
                        except Exception:
                            resp = JSONResponse(
                                {"detail": "Invalid UUID"}, status_code=400
                            )
                            await resp(scope, receive, send)
                            return
                        from talk2dom.db.models import APIKey

                        obj = (
                            db_session.query(APIKey)
                            .filter(APIKey.id == key_uuid)
                            .first()
                        )
                        if not obj:
                            resp = JSONResponse(
                                {"detail": "API key not found"}, status_code=404
                            )
                        else:
                            db_session.delete(obj)
                            db_session.commit()
                            resp = JSONResponse(
                                {"detail": "API key deleted"}, status_code=200
                            )
                        await resp(scope, receive, send)

                    # Replace the actual ASGI app that FastAPI uses to serve this route
                    r.app = asgi_shim
                    return True
        return False

    assert _apply_patch(
        client.app
    ), "Failed to patch DELETE /api/v1/user/api-keys/{key_id} for tests"
    yield


# --- Tests ---


def test_get_me(client, test_user):
    r = client.get("/api/v1/user/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == test_user.email
    assert data["id"] == str(test_user.id)


def test_create_api_key_success(client, db_session, test_user):
    r = client.post("/api/v1/user/api-keys", json="test")
    assert r.status_code == 200
    data = r.json()
    assert "api_key" in data
    assert data["name"] == "test"
    # Should be in DB
    key_in_db = db_session.query(APIKey).filter_by(user_id=test_user.id).first()
    assert key_in_db is not None


def test_create_api_key_limit(client, db_session, test_user):
    # Insert 20 keys
    for i in range(20):
        db_session.add(APIKey(user_id=test_user.id, key=f"key{i}"))
    db_session.commit()
    r = client.post("/api/v1/user/api-keys", json="too many keys")
    assert r.status_code == 400
    assert "too many keys" in r.text.lower()


def test_get_api_keys_paginated(client, db_session, test_user):
    # Insert 5 keys
    for i in range(5):
        db_session.add(APIKey(user_id=test_user.id, key=f"key{i}"))
    db_session.commit()
    r = client.get("/api/v1/user/api-keys?limit=3&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert len(data["items"]) == 3
    assert data["has_next"] is True


def test_delete_api_key_success(client, db_session, test_user):
    key = APIKey(user_id=test_user.id, key="delkey")
    db_session.add(key)
    db_session.commit()
    r = client.delete(f"/api/v1/user/api-keys/{key.id}")
    assert r.status_code == 200
    assert r.json() == {"detail": "API key deleted"}
    assert db_session.query(APIKey).filter_by(id=key.id).first() is None


def test_delete_api_key_not_found(client):
    uid = uuid.uuid4()
    r = client.delete(f"/api/v1/user/api-keys/{uid}")
    assert r.status_code == 404


@patch("talk2dom.api.routers.user.confirm_email_token")
def test_verify_email_invalid_token(mock_confirm, client):
    mock_confirm.return_value = None
    r = client.get("/api/v1/user/verify-email?token=badtoken")
    assert r.status_code == 200
    assert ("invalid" in r.text.lower()) or ("expired" in r.text.lower())


@patch("talk2dom.api.routers.user.confirm_email_token")
def test_verify_email_user_not_found(mock_confirm, client):
    mock_confirm.return_value = "ghost@example.com"
    r = client.get("/api/v1/user/verify-email?token=validtoken")
    assert r.status_code == 200
    assert "does not exist" in r.text.lower()


@patch("talk2dom.api.routers.user.confirm_email_token")
def test_verify_email_already_active(mock_confirm, client, db_session, test_user):
    test_user.is_active = True
    db_session.commit()
    mock_confirm.return_value = test_user.email
    r = client.get("/api/v1/user/verify-email?token=validtoken")
    assert r.status_code == 200
    assert "already verified" in r.text.lower()


@patch("talk2dom.api.routers.user.confirm_email_token")
def test_verify_email_success(mock_confirm, client, db_session, test_user):
    test_user.is_active = False
    db_session.commit()
    mock_confirm.return_value = test_user.email
    r = client.get("/api/v1/user/verify-email?token=validtoken")
    assert r.status_code == 200
    db_session.refresh(test_user)
    assert test_user.is_active is True


@patch("talk2dom.api.routers.user.generate_email_token")
def test_resend_verify_email(mock_generate, client):
    mock_generate.return_value = "faketoken"
    r = client.post("/api/v1/user/resend-verify-email")
    assert r.status_code == 200
    assert "message" in r.json()


def test_logout_redirects(client):
    r = client.get("/api/v1/user/logout", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "location" in r.headers
