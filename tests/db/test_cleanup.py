from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from talk2dom.db.cleanup import cleanup_api_usage
from talk2dom.db.models import APIUsage, Base, Project, User


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine)
    return testing_session_local()


def create_user(db, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        provider_user_id=f"provider:{email}",
        provider="local",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


def create_project(db, owner_id) -> Project:
    project = Project(id=uuid.uuid4(), name="project", owner_id=owner_id)
    db.add(project)
    db.commit()
    return project


def create_api_usage(
    db,
    user_id,
    request_time: datetime,
    project_id=None,
) -> APIUsage:
    usage = APIUsage(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        endpoint="/api/v1/locator",
        request_time=request_time,
        status_code=200,
        call_llm=False,
    )
    db.add(usage)
    db.commit()
    return usage


def test_cleanup_api_usage_dry_run_counts_without_deleting():
    db = make_session()
    user = create_user(db, "dry-run@example.com")
    create_api_usage(db, user.id, utcnow() - timedelta(days=40))
    create_api_usage(db, user.id, utcnow() - timedelta(days=5))

    result = cleanup_api_usage(db, older_than_days=30, dry_run=True)

    assert result.dry_run is True
    assert result.matched_rows == 1
    assert result.deleted_rows == 0
    assert db.query(APIUsage).count() == 2


def test_cleanup_api_usage_deletes_old_rows_only():
    db = make_session()
    user = create_user(db, "delete@example.com")
    old_usage = create_api_usage(db, user.id, utcnow() - timedelta(days=45))
    recent_usage = create_api_usage(db, user.id, utcnow() - timedelta(days=2))
    old_usage_id = old_usage.id
    recent_usage_id = recent_usage.id

    result = cleanup_api_usage(db, older_than_days=30, dry_run=False, batch_size=1)

    assert result.dry_run is False
    assert result.matched_rows == 1
    assert result.deleted_rows == 1
    remaining_ids = {row.id for row in db.query(APIUsage).all()}
    assert old_usage_id not in remaining_ids
    assert recent_usage_id in remaining_ids


def test_cleanup_api_usage_can_scope_to_project():
    db = make_session()
    user = create_user(db, "project@example.com")
    project_a = create_project(db, user.id)
    project_b = create_project(db, user.id)
    old_time = utcnow() - timedelta(days=60)

    scoped_usage = create_api_usage(db, user.id, old_time, project_id=project_a.id)
    unscoped_usage = create_api_usage(db, user.id, old_time, project_id=project_b.id)
    scoped_usage_id = scoped_usage.id
    unscoped_usage_id = unscoped_usage.id

    result = cleanup_api_usage(
        db,
        older_than_days=30,
        dry_run=False,
        project_id=project_a.id,
    )

    assert result.matched_rows == 1
    assert result.deleted_rows == 1
    remaining_ids = {row.id for row in db.query(APIUsage).all()}
    assert scoped_usage_id not in remaining_ids
    assert unscoped_usage_id in remaining_ids


def test_cleanup_api_usage_can_scope_to_user_email():
    db = make_session()
    target_user = create_user(db, "target@example.com")
    other_user = create_user(db, "other@example.com")
    old_time = utcnow() - timedelta(days=60)

    target_usage = create_api_usage(db, target_user.id, old_time)
    other_usage = create_api_usage(db, other_user.id, old_time)
    target_usage_id = target_usage.id
    other_usage_id = other_usage.id

    result = cleanup_api_usage(
        db,
        older_than_days=30,
        dry_run=False,
        user_email="target@example.com",
    )

    assert result.matched_rows == 1
    assert result.deleted_rows == 1
    remaining_ids = {row.id for row in db.query(APIUsage).all()}
    assert target_usage_id not in remaining_ids
    assert other_usage_id in remaining_ids
