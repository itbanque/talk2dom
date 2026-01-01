import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from talk2dom.api import deps
from talk2dom.db.models import Base, User, Project, ProjectInvite, ProjectMembership


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


def test_consume_credit_uses_subscription_then_one_time():
    db = make_session()
    user = User(
        email="a@example.com",
        provider_user_id="local:a",
        subscription_credits=1,
        one_time_credits=2,
    )
    db.add(user)
    db.commit()

    deps.consume_credit(db, user, amount=2)
    assert user.subscription_credits == 0
    assert user.one_time_credits == 1


def test_consume_credit_insufficient_raises():
    db = make_session()
    user = User(
        email="a@example.com",
        provider_user_id="local:a",
        subscription_credits=0,
        one_time_credits=0,
    )
    db.add(user)
    db.commit()

    with pytest.raises(HTTPException):
        deps.consume_credit(db, user, amount=1)


def test_has_project_access_owner_and_member():
    db = make_session()
    owner = User(email="o@example.com", provider_user_id="local:o")
    member = User(email="m@example.com", provider_user_id="local:m")
    db.add_all([owner, member])
    db.commit()

    project = Project(name="P", owner_id=owner.id)
    db.add(project)
    db.commit()

    assert deps.has_project_access(db, owner.id, project.id) is True

    db.add(ProjectMembership(user_id=member.id, project_id=project.id))
    db.commit()

    assert deps.has_project_access(db, member.id, project.id) is True


def test_handle_pending_invites_creates_membership():
    db = make_session()
    owner = User(email="owner@example.com", provider_user_id="local:o", plan="pro")
    invited = User(email="invite@example.com", provider_user_id="local:i")
    db.add_all([owner, invited])
    db.commit()

    project = Project(name="P", owner_id=owner.id)
    db.add(project)
    db.commit()

    invite = ProjectInvite(
        project_id=project.id,
        email=invited.email,
        invited_by_user_id=owner.id,
    )
    db.add(invite)
    db.commit()

    deps.handle_pending_invites(db, invited)

    membership = (
        db.query(ProjectMembership)
        .filter_by(user_id=invited.id, project_id=project.id)
        .first()
    )
    assert membership is not None
    refreshed_invite = db.query(ProjectInvite).first()
    assert refreshed_invite.accepted is True
