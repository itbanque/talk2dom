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

from datetime import datetime, timedelta

from talk2dom.api.main import app
from talk2dom.api.limiter import limiter
from talk2dom.api.routers.admin import require_admin
from talk2dom.db.models import (
    APIKey,
    APIUsage,
    Base,
    HTML,
    Project,
    ProjectInvite,
    ProjectMembership,
    UILocatorCache,
    User,
)
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
    limiter.reset()  # login is rate-limited per address; tests share one

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


def test_user_page_shows_usage_chart(client, db_session, test_user):
    now = datetime.utcnow()
    for offset_days, count in [(0, 3), (5, 1), (40, 1)]:  # day 40 is out of window
        for _ in range(count):
            db_session.add(
                APIUsage(
                    user_id=test_user.id,
                    endpoint="/api/v1/inference/locator",
                    request_time=now - timedelta(days=offset_days),
                    status_code=200,
                    call_llm=True,
                )
            )
    db_session.commit()

    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    assert page.status_code == 200
    assert "usage-chart" in page.text
    # subtitle: 4 calls in window, 5 all-time
    assert "last 30 days · 4 calls · 5 all-time" in page.text
    # tooltip labels for the two in-window days
    assert "· 3 calls" in page.text
    assert "· 1 calls" in page.text


def test_locator_call_records_meta(client, db_session, test_user, monkeypatch):
    from types import SimpleNamespace
    from talk2dom.api.routers import inference
    from talk2dom.api.deps import get_current_user

    monkeypatch.setattr(
        inference, "get_cached_locator", lambda *a, **k: (None, None, None)
    )
    monkeypatch.setattr(
        inference,
        "call_selector_llm",
        lambda *a, **k: SimpleNamespace(
            action_type="click",
            action_value="",
            selector_type="css selector",
            selector_value="button#plus",
        ),
    )
    monkeypatch.setattr(inference, "save_locator", lambda *a, **k: None)
    app.dependency_overrides[get_current_user] = lambda: test_user

    resp = client.post(
        "/api/v1/inference/locator-playground",
        json={
            "url": "https://claude.ai/new?utm=x",
            "html": "<html><body><button id='plus'>+</button></body></html>",
            "user_instruction": "locate the + button",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["selector_value"] == "button#plus"

    usage = db_session.query(APIUsage).filter_by(user_id=test_user.id).one()
    assert usage.meta_data["url"] == "https://claude.ai/new"  # query stripped
    assert usage.meta_data["user_instruction"] == "locate the + button"
    assert usage.meta_data["selector_type"] == "css selector"
    assert usage.meta_data["selector_value"] == "button#plus"
    assert usage.meta_data["cache_hit"] is False
    assert usage.call_llm is True

    import hashlib

    assert (
        usage.meta_data["html_id"]
        == hashlib.sha256(b"https://claude.ai/new").hexdigest()
    )

    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    assert "usage-chart" in page.text
    assert "· 1 calls" in page.text  # today's call shows up in the chart
    # the playground call appears under Located elements via usage meta
    assert "locate the + button" in page.text
    assert "css selector=button#plus" in page.text
    assert "Playground" in page.text


@pytest.fixture
def cache_entry(db_session, test_user):
    project = Project(id=uuid.uuid4(), name="lizong", owner_id=test_user.id)
    html_id = "b" * 64
    db_session.add(project)
    db_session.add(
        HTML(
            id=html_id,
            url="https://claude.ai/new",
            backbone="<html><body><button id='voice'>Voice</button></body></html>",
            row_html="<html><body><button id='voice'>Voice</button></body></html>",
        )
    )
    entry = UILocatorCache(
        id="c" * 64,
        url="https://claude.ai/new",
        user_instruction="locate the voice mode button",
        html_id=html_id,
        selector_type="css selector",
        selector_value="button#voice",
        action="click:",
        project_id=project.id,
    )
    db_session.add(entry)
    db_session.commit()
    return entry


def test_user_page_shows_cached_locators(client, cache_entry, test_user):
    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    assert page.status_code == 200
    assert "locate the voice mode button" in page.text
    assert "css selector=button#voice" in page.text
    assert f"/admin/cache/{cache_entry.id}/snapshot" in page.text


def test_cache_snapshot_renders_with_highlight(client, cache_entry):
    login(client)
    resp = client.get(f"/admin/cache/{cache_entry.id}/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-security-policy"] == "sandbox allow-scripts"
    assert "<button id='voice'>Voice</button>" in resp.text
    assert '"button#voice"' in resp.text


def test_located_elements_playground_and_project_filter(
    client, db_session, test_user, cache_entry
):
    db_session.add(
        HTML(
            id="d" * 64,
            url="https://x.dev/app",
            backbone="<button id='go'>Go</button>",
            row_html="<html><body><button id='go'>Go</button></body></html>",
        )
    )
    db_session.add(
        APIUsage(
            user_id=test_user.id,
            endpoint="/api/v1/inference/locator-playground",
            request_time=datetime.utcnow(),
            status_code=200,
            call_llm=True,
            meta_data={
                "url": "https://x.dev/app",
                "user_instruction": "locate the go button",
                "html_id": "d" * 64,
                "selector_type": "css selector",
                "selector_value": "button#go",
                "action_type": "",
                "action_value": "",
                "cache_hit": False,
            },
        )
    )
    db_session.commit()
    login(client)

    # no filter: both the playground call (usage meta) and the project cache entry
    page = client.get(f"/admin/users/{test_user.id}")
    assert "locate the go button" in page.text
    assert "locate the voice mode button" in page.text
    assert "Playground" in page.text

    # playground only
    page = client.get(f"/admin/users/{test_user.id}", params={"project": "none"})
    assert "locate the go button" in page.text
    assert "locate the voice mode button" not in page.text

    # specific project only
    page = client.get(
        f"/admin/users/{test_user.id}",
        params={"project": str(cache_entry.project_id)},
    )
    assert "locate the go button" not in page.text
    assert "locate the voice mode button" in page.text


def test_located_elements_dedup_cache_and_meta(db_session, test_user):
    from talk2dom.api.routers.admin import _located_elements
    from talk2dom.db.cache import compute_locator_id

    project = Project(id=uuid.uuid4(), name="p1", owner_id=test_user.id)
    db_session.add(project)
    html_id = "e" * 64
    loc_id = compute_locator_id("locate x", html_id, "https://a.dev/", str(project.id))
    db_session.add(
        UILocatorCache(
            id=loc_id,
            url="https://a.dev/",
            user_instruction="locate x",
            html_id=html_id,
            selector_type="css selector",
            selector_value="#x",
            action="click:",
            project_id=project.id,
        )
    )
    db_session.add(
        APIUsage(
            user_id=test_user.id,
            project_id=project.id,
            endpoint="/api/v1/inference/locator",
            request_time=datetime.utcnow(),
            status_code=200,
            call_llm=True,
            meta_data={
                "url": "https://a.dev/",
                "user_instruction": "locate x",
                "html_id": html_id,
                "selector_type": "css selector",
                "selector_value": "#x",
            },
        )
    )
    db_session.commit()

    rows = _located_elements(db_session, test_user, "", {project.id: "p1"})
    assert len(rows) == 1  # the call collapses into its cache entry
    assert rows[0]["snapshot_url"].startswith("/admin/cache/")


def test_usage_snapshot_from_meta(client, db_session, test_user):
    html_id = "a" * 64
    db_session.add(
        HTML(
            id=html_id,
            url="https://claude.ai/new",
            backbone="<button id='plus'>+</button>",
            row_html="<html><body><button id='plus'>+</button></body></html>",
        )
    )
    usage = APIUsage(
        user_id=test_user.id,
        endpoint="/api/v1/inference/locator-playground",
        status_code=200,
        call_llm=True,
        meta_data={
            "url": "https://claude.ai/new",
            "user_instruction": "locate the + button",
            "html_id": html_id,
            "selector_type": "css selector",
            "selector_value": "button#plus",
        },
    )
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    login(client)
    resp = client.get(f"/admin/usage/{usage.id}/snapshot")
    assert resp.status_code == 200
    assert resp.headers["content-security-policy"] == "sandbox allow-scripts"
    assert "<button id='plus'>+</button>" in resp.text
    assert '"button#plus"' in resp.text


def test_cache_snapshot_requires_login(client, cache_entry):
    resp = client.get(f"/admin/cache/{cache_entry.id}/snapshot", follow_redirects=False)
    assert resp.status_code == 303


def test_delete_cache_entry(client, db_session, test_user, cache_entry):
    login(client)
    page = client.get(f"/admin/users/{test_user.id}")
    csrf = re.search(r'name="csrf_token" value="([0-9a-f]+)"', page.text).group(1)

    resp = client.post(
        f"/admin/cache/{cache_entry.id}/delete",
        data={"csrf_token": csrf, "user_id": str(test_user.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/admin/users/{test_user.id}"
    assert db_session.query(UILocatorCache).count() == 0


def _csrf(client, user_id):
    page = client.get(f"/admin/users/{user_id}")
    return re.search(r'name="csrf_token" value="([0-9a-f]+)"', page.text).group(1)


def test_admin_create_project_and_api_key(client, db_session, test_user):
    login(client)
    csrf = _csrf(client, test_user.id)

    resp = client.post(
        f"/admin/users/{test_user.id}/projects",
        data={"csrf_token": csrf, "name": "growth"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    project = db_session.query(Project).filter_by(owner_id=test_user.id).one()
    assert project.name == "growth"
    membership = (
        db_session.query(ProjectMembership)
        .filter_by(project_id=project.id, user_id=test_user.id)
        .one()
    )
    assert membership.role == "owner"

    resp = client.post(
        f"/admin/users/{test_user.id}/api-keys",
        data={"csrf_token": csrf, "name": "ci-bot"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    key = db_session.query(APIKey).filter_by(user_id=test_user.id).one()
    assert key.name == "ci-bot"
    assert len(key.key) == 64

    page = client.get(f"/admin/users/{test_user.id}")
    assert "growth" in page.text
    assert key.key in page.text


def test_admin_create_project_requires_name(client, db_session, test_user):
    login(client)
    csrf = _csrf(client, test_user.id)
    resp = client.post(
        f"/admin/users/{test_user.id}/projects",
        data={"csrf_token": csrf, "name": "   "},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
    assert db_session.query(Project).count() == 0


def test_admin_invite_existing_user_joins_directly(client, db_session, test_user):
    project = Project(id=uuid.uuid4(), name="team", owner_id=test_user.id)
    other = User(
        id=uuid.uuid4(),
        provider_user_id="other-provider-id",
        email="other@example.com",
        is_active=True,
    )
    db_session.add_all(
        [
            project,
            other,
            ProjectMembership(
                user_id=test_user.id, project_id=project.id, role="owner"
            ),
        ]
    )
    db_session.commit()
    login(client)
    csrf = _csrf(client, test_user.id)

    invite_data = {
        "csrf_token": csrf,
        "project_id": str(project.id),
        "email": "other@example.com",
    }
    resp = client.post(
        f"/admin/users/{test_user.id}/invite",
        data=invite_data,
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "saved=1" in resp.headers["location"]
    membership = (
        db_session.query(ProjectMembership)
        .filter_by(project_id=project.id, user_id=other.id)
        .one()
    )
    assert membership.role == "member"
    invite = db_session.query(ProjectInvite).filter_by(project_id=project.id).one()
    assert invite.accepted is True

    # inviting again → already a member
    resp = client.post(
        f"/admin/users/{test_user.id}/invite",
        data=invite_data,
        follow_redirects=False,
    )
    assert "error=" in resp.headers["location"]

    # member shows on the page and can be removed
    page = client.get(f"/admin/users/{test_user.id}")
    assert "other@example.com" in page.text
    resp = client.post(
        f"/admin/memberships/{membership.id}/delete",
        data={"csrf_token": csrf, "user_id": str(test_user.id)},
        follow_redirects=False,
    )
    assert "saved=1" in resp.headers["location"]
    assert (
        db_session.query(ProjectMembership)
        .filter_by(project_id=project.id, user_id=other.id)
        .count()
        == 0
    )

    # owner membership is protected
    owner_membership = (
        db_session.query(ProjectMembership)
        .filter_by(project_id=project.id, user_id=test_user.id)
        .one()
    )
    resp = client.post(
        f"/admin/memberships/{owner_membership.id}/delete",
        data={"csrf_token": csrf, "user_id": str(test_user.id)},
        follow_redirects=False,
    )
    assert "error=" in resp.headers["location"]
    assert (
        db_session.query(ProjectMembership).filter_by(id=owner_membership.id).count()
        == 1
    )


def test_admin_invite_unregistered_email_pending_and_revoke(
    client, db_session, test_user
):
    project = Project(id=uuid.uuid4(), name="team", owner_id=test_user.id)
    db_session.add_all(
        [
            project,
            ProjectMembership(
                user_id=test_user.id, project_id=project.id, role="owner"
            ),
        ]
    )
    db_session.commit()
    login(client)
    csrf = _csrf(client, test_user.id)

    resp = client.post(
        f"/admin/users/{test_user.id}/invite",
        data={
            "csrf_token": csrf,
            "project_id": str(project.id),
            "email": "newbie@example.com",
        },
        follow_redirects=False,
    )
    assert "saved=1" in resp.headers["location"]
    invite = db_session.query(ProjectInvite).filter_by(email="newbie@example.com").one()
    assert invite.accepted is False

    page = client.get(f"/admin/users/{test_user.id}")
    assert "newbie@example.com" in page.text  # pending invites column

    resp = client.post(
        f"/admin/invites/{invite.id}/delete",
        data={"csrf_token": csrf, "user_id": str(test_user.id)},
        follow_redirects=False,
    )
    assert "saved=1" in resp.headers["location"]
    assert db_session.query(ProjectInvite).count() == 0


def test_admin_delete_api_key(client, db_session, test_user):
    key = APIKey(user_id=test_user.id, key="k" * 64, name="old-key")
    db_session.add(key)
    db_session.commit()
    db_session.refresh(key)
    login(client)
    csrf = _csrf(client, test_user.id)

    resp = client.post(
        f"/admin/api-keys/{key.id}/delete",
        data={"csrf_token": csrf, "user_id": str(test_user.id)},
        follow_redirects=False,
    )
    assert "saved=1" in resp.headers["location"]
    assert db_session.query(APIKey).count() == 0


def _list_csrf(client):
    page = client.get("/admin/")
    return re.search(r'name="csrf_token" value="([0-9a-f]+)"', page.text).group(1)


def test_admin_create_user_with_password(client, db_session):
    from talk2dom.api.utils import hash_helper

    login(client)
    csrf = _list_csrf(client)

    resp = client.post(
        "/admin/create-user",
        data={
            "csrf_token": csrf,
            "email": "Manual@Example.com",
            "password": "s3cret-pass",
            "name": "Manual User",
            "plan": "pro",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    user = db_session.query(User).filter_by(email="manual@example.com").one()
    assert resp.headers["location"] == f"/admin/users/{user.id}?saved=1"
    assert user.provider == "credentials"
    assert user.provider_user_id == "local:manual@example.com"
    assert user.plan == "pro"
    assert user.is_active is True
    assert hash_helper.verify_password("s3cret-pass", user.hashed_password)

    # duplicate email rejected
    resp = client.post(
        "/admin/create-user",
        data={"csrf_token": csrf, "email": "manual@example.com", "password": "x" * 8},
        follow_redirects=False,
    )
    assert "error=Email+already+registered" in resp.headers["location"]

    # short password rejected
    resp = client.post(
        "/admin/create-user",
        data={"csrf_token": csrf, "email": "another@example.com", "password": "short"},
        follow_redirects=False,
    )
    assert "error=" in resp.headers["location"]
    assert db_session.query(User).filter_by(email="another@example.com").count() == 0


def test_admin_create_user_accepts_pending_invites(client, db_session, test_user):
    test_user.plan = "pro"  # inviter plan gates pending-invite acceptance
    project = Project(id=uuid.uuid4(), name="team", owner_id=test_user.id)
    db_session.add_all(
        [
            project,
            ProjectMembership(
                user_id=test_user.id, project_id=project.id, role="owner"
            ),
            ProjectInvite(
                project_id=project.id,
                email="invited@example.com",
                invited_by_user_id=test_user.id,
            ),
        ]
    )
    db_session.commit()
    login(client)
    csrf = _list_csrf(client)

    resp = client.post(
        "/admin/create-user",
        data={
            "csrf_token": csrf,
            "email": "invited@example.com",
            "password": "s3cret-pass",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    new_user = db_session.query(User).filter_by(email="invited@example.com").one()
    assert (
        db_session.query(ProjectMembership)
        .filter_by(user_id=new_user.id, project_id=project.id)
        .count()
        == 1
    )


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
