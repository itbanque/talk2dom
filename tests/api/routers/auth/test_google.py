import os
import uuid
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
import pytest


@pytest.fixture(scope="function")
def app(monkeypatch):
    """Build a tiny FastAPI app with the Google auth router mounted,
    and patch external dependencies so tests are hermetic.
    """
    # Ensure UI_DOMAIN is set for the post-login redirect
    os.environ["UI_DOMAIN"] = "http://ui.example"

    # ---- Async stubs & state capture for oauth.google ----
    class _OAuthGoogle:
        def __init__(self):
            self._last_redirect_uri = None

        async def authorize_redirect(self, request: Request, redirect_uri: str):
            # Capture the redirect_uri for assertions
            self._last_redirect_uri = redirect_uri
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")

        async def authorize_access_token(self, request: Request):
            # Simulate Google returning a token + userinfo
            return {
                "access_token": "fake-token",
                "userinfo": {
                    "sub": "google-sub-123",
                    "email": "alice@example.com",
                    "name": "Alice",
                },
            }

    fake_google = _OAuthGoogle()

    # Patch the oauth object used by the router
    from talk2dom.api.auth import google_oauth as google_oauth_mod
    from talk2dom.api.routers.auth import google as google_router

    fake_oauth_obj = type("_O", (), {"google": fake_google})()
    monkeypatch.setattr(google_oauth_mod, "oauth", fake_oauth_obj)
    monkeypatch.setattr(google_router, "oauth", fake_oauth_obj)

    # Patch DB dependency to a dummy (handlers don't use it directly in login; in callback
    # it's only passed to downstream functions that we also patch)
    dummy_db = object()
    from talk2dom.db.session import get_db as real_get_db

    async def _get_db_override():
        yield dummy_db

    # Patch handle_pending_invites to observe it was called
    called = {"flag": False, "db": None, "user_id": None}

    def fake_handle_pending_invites(db, user):
        called["flag"] = True
        called["db"] = db
        called["user_id"] = str(user.id)

    monkeypatch.setattr(
        "talk2dom.api.deps.handle_pending_invites", fake_handle_pending_invites
    )

    # Patch User.get_or_create_google_user to avoid real DB work
    from talk2dom.db import models as models_mod

    class FakeUser:
        def __init__(self):
            self.id = uuid.uuid4()
            self.email = "alice@example.com"
            self.name = "Alice"

    async def fake_get_or_create_google_user(db, user_info):
        assert db is dummy_db
        assert user_info["email"] == "alice@example.com"
        return FakeUser()

    monkeypatch.setattr(
        models_mod.User,
        "get_or_create_google_user",
        staticmethod(fake_get_or_create_google_user),
    )

    # Build app and mount router
    app = FastAPI()
    from talk2dom.api.routers.auth import google as google_router

    monkeypatch.setattr(
        google_router, "handle_pending_invites", fake_handle_pending_invites
    )

    app.include_router(google_router.router, prefix="/auth")

    # Add session middleware because router writes request.session["user"]
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie="google_test_session",
    )

    # Expose test hooks on app.state for assertions
    app.state._oauth_google = fake_google
    app.state._pending_called = called

    # Helper route to inspect session after callback
    @app.get("/_session_user")
    def _session_user(request: Request):
        return request.session.get("user")

    # Override get_db dependency
    app.dependency_overrides[real_get_db] = _get_db_override

    return app


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


def test_google_login_redirects_and_builds_callback_uri(client, app):
    r = client.get("/auth/google/login", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("https://accounts.google.com/")

    # The router should have constructed a callback URL ending with /auth/google/callback
    cb = app.state._oauth_google._last_redirect_uri
    assert str(cb).endswith("/auth/google/callback")


def test_google_callback_sets_session_and_redirects_to_ui(client, app):
    r = client.get("/auth/google/callback", follow_redirects=False)
    # Should redirect to UI_DOMAIN/projects
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "http://ui.example/projects"

    # Session should contain user dict with string id, email, name, provider=google
    r2 = client.get("/_session_user")
    assert r2.status_code == 200
    data = r2.json()
    assert set(["id", "email", "name", "provider"]).issubset(data.keys())
    # id is str(uuid)
    assert isinstance(data["id"], str) and len(data["id"]) > 0
    assert data["email"] == "alice@example.com"
    assert data["name"] == "Alice"
    assert data["provider"] == "google"

    # handle_pending_invites should have been called with our dummy db and user
    pc = app.state._pending_called
    assert pc["flag"] is True
    assert pc["db"] is not None
    assert isinstance(pc["user_id"], str)
