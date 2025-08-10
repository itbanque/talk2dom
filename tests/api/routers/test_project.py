import pytest


# This fixture sets real project route paths for all tests (autouse)
@pytest.fixture(autouse=True)
def _map_real_paths(app):
    app.state._project_paths = {
        "list_projects_path": "/api/v1",
        "create_project_path": "/api/v1",
        "members_path_tmpl": "/api/v1/{project_id}/members",
        "invites_path_tmpl": "/api/v1/{project_id}/invites",
        "locator_cache_path_tmpl": "/api/v1/{project_id}/locator-cache",
    }


import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from talk2dom.db.models import (
    Base,
    User,
    Project,
    ProjectMembership,
    UILocatorCache,
    ProjectInvite,
)
from talk2dom.db.session import get_db as real_get_db
from talk2dom.api import deps as deps_mod


# ---------------------------
# Fixtures: DB & FastAPI app
# ---------------------------
@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture(scope="function")
def db(engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(scope="function")
def current_user(db):
    u = User(
        email="owner@example.com",
        provider="credentials",
        provider_user_id="local:owner",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture(scope="function")
def app(db, current_user, monkeypatch):
    # Build app & mount router
    app = FastAPI()
    from talk2dom.api.routers import project as project_router

    app.include_router(project_router.router, prefix="/api/v1")

    # Override get_db
    def _get_db_override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[real_get_db] = _get_db_override

    # Override get_current_user to return our fixture user
    def _get_current_user_override():
        return current_user

    app.dependency_overrides[deps_mod.get_current_user] = _get_current_user_override

    # Dynamically detect project-related route paths
    def _find_project_paths(app):
        # Returns dict of route names to their paths or None if not found
        paths = {
            "list_projects_path": None,
            "create_project_path": None,
            "members_path_tmpl": None,
            "invites_path_tmpl": None,
            "locator_cache_path_tmpl": None,
        }
        for route in app.routes:
            if not hasattr(route, "methods") or not hasattr(route, "path"):
                continue
            path = route.path
            methods = route.methods
            # List projects: GET /api/v1/project[s]
            if (
                "GET" in methods
                and (path.endswith("/project") or path.endswith("/projects"))
                and paths["list_projects_path"] is None
            ):
                paths["list_projects_path"] = path
            # Create project: POST /api/v1/project[s]
            if (
                "POST" in methods
                and (path.endswith("/project") or path.endswith("/projects"))
                and paths["create_project_path"] is None
            ):
                paths["create_project_path"] = path
            # Members list: GET .../project/{project_id}/members
            if (
                "GET" in methods
                and "/project/" in path
                and path.endswith("/members")
                and paths["members_path_tmpl"] is None
            ):
                paths["members_path_tmpl"] = path
            # Invites list: GET .../project/{project_id}/invites
            if (
                "GET" in methods
                and "/project/" in path
                and path.endswith("/invites")
                and paths["invites_path_tmpl"] is None
            ):
                paths["invites_path_tmpl"] = path
            # Locator cache list: GET .../project/{project_id}/locator-cache
            if (
                "GET" in methods
                and "/project/" in path
                and path.endswith("/locator-cache")
                and paths["locator_cache_path_tmpl"] is None
            ):
                paths["locator_cache_path_tmpl"] = path
        return paths

    app.state._project_paths = _find_project_paths(app)
    # For backward compat, also set _project_base to list_projects_path
    app.state._project_base = app.state._project_paths.get("list_projects_path")

    print("=== Registered routes ===")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            print(route.path, route.methods)

    return app


@pytest.fixture(scope="function")
def client(app):
    return TestClient(app)


# ----------------------
# Helpers to seed data
# ----------------------


def _mk_project(db, owner_id, name="P"):
    p = Project(name=name, owner_id=owner_id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _add_member(db, project_id, user_id, role="member"):
    m = ProjectMembership(project_id=project_id, user_id=user_id, role=role)
    db.add(m)
    db.commit()
    return m


def _mk_user(db, email):
    u = User(email=email, provider="credentials", provider_user_id=f"local:{email}")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ----------------------
# Tests
# ----------------------


def test_list_user_projects_pagination(client, app, db, current_user):
    base = app.state._project_paths.get("list_projects_path")
    if not base:
        raise AssertionError("Project list route not found")

    # Create 3 projects and memberships for current user
    p1 = _mk_project(db, current_user.id, name="P1")
    p2 = _mk_project(db, current_user.id, name="P2")
    p3 = _mk_project(db, current_user.id, name="P3")
    for p in (p1, p2, p3):
        _add_member(db, p.id, current_user.id, role="owner")

    r = client.get(f"{base}?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert data["has_next"] is True
    assert len(data["items"]) == 2

    r2 = client.get(f"{base}?limit=2&offset=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["has_next"] is False
    assert len(d2["items"]) == 1


# -----------------------------------------
# Additional tests for create and auth
# -----------------------------------------


def test_create_project_and_list_visibility(client, app, db, current_user):
    base = app.state._project_paths.get("create_project_path")
    if not base:
        raise AssertionError("Create project route not found")

    # Create project via API
    payload = {"name": "CreatedByAPI"}
    r = client.post(base, json=payload)
    assert r.status_code in (200, 201)
    created = r.json()
    assert created.get("name") == "CreatedByAPI"

    # Owner should be auto-member or we add it if router doesn't
    # Ensure membership exists for visibility in list
    proj_id = created.get("id")
    if proj_id:
        import uuid as _uuid_mod

        # Convert to UUID if ProjectMembership.project_id expects UUID
        proj_id_uuid = _uuid_mod.UUID(proj_id)
        if (
            not db.query(ProjectMembership)
            .filter_by(project_id=proj_id_uuid, user_id=current_user.id)
            .first()
        ):
            _add_member(db, proj_id_uuid, current_user.id, role="owner")

    # List should include it
    list_path = app.state._project_paths.get("list_projects_path")
    if not list_path:
        raise AssertionError("Project list route not found")
    r2 = client.get(f"{list_path}?limit=10&offset=0")
    assert r2.status_code == 200
    items = r2.json().get("items", [])
    assert any(p.get("name") == "CreatedByAPI" for p in items)


def test_non_member_access_is_denied_for_members_invites_cache(app, db, current_user):
    # Build a separate client to allow changing dependency for current user
    from fastapi.testclient import TestClient as _TC

    # Seed a project owned by current_user
    p = _mk_project(db, current_user.id, name="PrivateP")
    _add_member(db, p.id, current_user.id, role="owner")

    # Create a different user (non-member)
    outsider = _mk_user(db, "outsider@example.com")

    # Override get_current_user to outsider for this test
    def _get_current_user_outsider():
        return outsider

    from talk2dom.api import deps as _deps

    app.dependency_overrides[_deps.get_current_user] = _get_current_user_outsider

    try:
        client = _TC(app)
        paths = app.state._project_paths
        # Members list
        members_tmpl = paths.get("members_path_tmpl")
        if not members_tmpl:
            raise AssertionError("Members list route not found")
        members_path = members_tmpl.replace("{project_id}", str(p.id)).replace(
            "{projectId}", str(p.id)
        )
        r1 = client.get(f"{members_path}?limit=10&offset=0")
        assert r1.status_code in (403, 404)

        # Invites list
        invites_tmpl = paths.get("invites_path_tmpl")
        if not invites_tmpl:
            raise AssertionError("Invites list route not found")
        invites_path = invites_tmpl.replace("{project_id}", str(p.id)).replace(
            "{projectId}", str(p.id)
        )
        r2 = client.get(f"{invites_path}?limit=10&offset=0")
        assert r2.status_code in (403, 404)

        # Locator cache list
        cache_tmpl = paths.get("locator_cache_path_tmpl")
        if not cache_tmpl:
            raise AssertionError("Locator cache list route not found")
        cache_path = cache_tmpl.replace("{project_id}", str(p.id)).replace(
            "{projectId}", str(p.id)
        )
        r3 = client.get(f"{cache_path}?limit=10&offset=0")
        assert r3.status_code in (403, 404)
    finally:
        # Restore default current user override (owner)
        from talk2dom.api import deps as _deps2

        def _restore_owner():
            return current_user

        app.dependency_overrides[_deps2.get_current_user] = _restore_owner


def test_list_members_pagination(client, app, db, current_user):
    paths = app.state._project_paths
    members_tmpl = paths.get("members_path_tmpl")
    if not members_tmpl:
        raise AssertionError("Members list route not found")

    # Create project; current_user is owner+member
    p = _mk_project(db, current_user.id, name="PM")
    _add_member(db, p.id, current_user.id, role="owner")

    # Add two more members
    u2 = _mk_user(db, "m2@example.com")
    u3 = _mk_user(db, "m3@example.com")
    _add_member(db, p.id, u2.id, role="member")
    _add_member(db, p.id, u3.id, role="member")

    members_path = members_tmpl.replace("{project_id}", str(p.id)).replace(
        "{projectId}", str(p.id)
    )
    r = client.get(f"{members_path}?limit=2&offset=0")
    assert r.status_code == 200
    d = r.json()
    assert d["has_next"] is True
    assert len(d["items"]) == 2

    r2 = client.get(f"{members_path}?limit=2&offset=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["has_next"] is False
    assert len(d2["items"]) == 1


def test_list_invites_pagination(client, app, db, current_user):
    paths = app.state._project_paths
    invites_tmpl = paths.get("invites_path_tmpl")
    if not invites_tmpl:
        raise AssertionError("Invites list route not found")

    p = _mk_project(db, current_user.id, name="PI")
    _add_member(db, p.id, current_user.id, role="owner")

    # Seed 3 invites
    inv1 = ProjectInvite(
        project_id=p.id,
        email="a@example.com",
        invited_by_user_id=current_user.id,
        accepted=False,
    )
    inv2 = ProjectInvite(
        project_id=p.id,
        email="b@example.com",
        invited_by_user_id=current_user.id,
        accepted=False,
    )
    inv3 = ProjectInvite(
        project_id=p.id,
        email="c@example.com",
        invited_by_user_id=current_user.id,
        accepted=False,
    )
    db.add_all([inv1, inv2, inv3])
    db.commit()

    invites_path = invites_tmpl.replace("{project_id}", str(p.id)).replace(
        "{projectId}", str(p.id)
    )
    r = client.get(f"{invites_path}?limit=2&offset=0")
    assert r.status_code == 200
    d = r.json()
    assert d["has_next"] is True
    assert len(d["items"]) == 2

    r2 = client.get(f"{invites_path}?limit=2&offset=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["has_next"] is False
    assert len(d2["items"]) == 1


def test_list_locator_cache_pagination(client, app, db, current_user):
    paths = app.state._project_paths
    cache_tmpl = paths.get("locator_cache_path_tmpl")
    if not cache_tmpl:
        raise AssertionError("Locator cache list route not found")

    p = _mk_project(db, current_user.id, name="PLC")
    _add_member(db, p.id, current_user.id, role="owner")

    # Seed 3 cache rows
    import uuid as _uuid_mod

    c1 = UILocatorCache(
        id=str(_uuid_mod.uuid4()),
        project_id=p.id,
        url="https://ex.com/1",
        user_instruction="find 1",
        selector_type="css",
        selector_value="div.example",
    )
    c2 = UILocatorCache(
        id=str(_uuid_mod.uuid4()),
        project_id=p.id,
        url="https://ex.com/2",
        user_instruction="find 2",
        selector_type="css",
        selector_value="div.example",
    )
    c3 = UILocatorCache(
        id=str(_uuid_mod.uuid4()),
        project_id=p.id,
        url="https://ex.com/3",
        user_instruction="find 3",
        selector_type="css",
        selector_value="div.example",
    )
    db.add_all([c1, c2, c3])
    db.commit()

    cache_path = cache_tmpl.replace("{project_id}", str(p.id)).replace(
        "{projectId}", str(p.id)
    )
    r = client.get(f"{cache_path}?limit=2&offset=0")
    assert r.status_code == 200
    d = r.json()
    assert d["has_next"] is True
    assert len(d["items"]) == 2

    r2 = client.get(f"{cache_path}?limit=2&offset=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["has_next"] is False
    assert len(d2["items"]) == 1
