import os
import secrets
import uuid

from talk2dom.db.models import Base
from talk2dom.db.models import APIKey, Project, ProjectMembership, User
from talk2dom.db.session import engine, SessionLocal
from loguru import logger


def _is_truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def seed_local_data():
    if not _is_truthy(os.getenv("LOCAL_SEED_ENABLED", "false")):
        return

    if SessionLocal is None or not callable(SessionLocal):
        logger.warning("Skipping local seed: no usable DB session.")
        return

    seed_email = os.getenv("LOCAL_SEED_EMAIL", "local@talk2dom.dev")
    seed_name = os.getenv("LOCAL_SEED_NAME", "Local Seed User")
    seed_provider_user_id = os.getenv("LOCAL_SEED_PROVIDER_USER_ID", "local:seed-user")
    seed_project_name = os.getenv("LOCAL_SEED_PROJECT_NAME", "Local Demo Project")
    seed_api_key = os.getenv("LOCAL_SEED_API_KEY", "t2d-local-api-key")
    seed_project_id_raw = os.getenv(
        "LOCAL_SEED_PROJECT_ID", "00000000-0000-0000-0000-000000000001"
    )
    seed_project_id = None
    if seed_project_id_raw:
        try:
            seed_project_id = uuid.UUID(seed_project_id_raw)
        except ValueError:
            logger.warning(
                f"Invalid LOCAL_SEED_PROJECT_ID ({seed_project_id_raw}), falling back to auto-generated UUID."
            )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == seed_email).first()
        if not user:
            user = User(
                email=seed_email,
                provider_user_id=seed_provider_user_id,
                name=seed_name,
                provider="local",
                is_active=True,
            )
            db.add(user)
            db.flush()

        if seed_project_id:
            project = db.query(Project).filter(Project.id == seed_project_id).first()
        else:
            project = None
        if not project:
            project = (
                db.query(Project)
                .filter(Project.owner_id == user.id, Project.name == seed_project_name)
                .first()
            )
        if not project:
            project_kwargs = {"name": seed_project_name, "owner_id": user.id}
            if seed_project_id:
                project_kwargs["id"] = seed_project_id
            project = Project(**project_kwargs)
            db.add(project)
            db.flush()

        membership = (
            db.query(ProjectMembership)
            .filter(
                ProjectMembership.user_id == user.id,
                ProjectMembership.project_id == project.id,
            )
            .first()
        )
        if not membership:
            db.add(
                ProjectMembership(user_id=user.id, project_id=project.id, role="owner")
            )

        local_key = (
            db.query(APIKey)
            .filter(APIKey.user_id == user.id, APIKey.name == "local-seed")
            .first()
        )
        if not local_key:
            key_conflict = db.query(APIKey).filter(APIKey.key == seed_api_key).first()
            key_value = seed_api_key if key_conflict is None else secrets.token_hex(32)
            db.add(APIKey(user_id=user.id, key=key_value, name="local-seed"))
        else:
            key_value = local_key.key

        db.commit()
        logger.info(
            f"Local seed ready: email={seed_email}, project_id={project.id}, project={seed_project_name}, api_key={key_value}"
        )
    except Exception as e:
        db.rollback()
        logger.warning(f"Local seed failed: {e}")
    finally:
        db.close()


def init_db():
    if SessionLocal is None:
        logger.warning("Skipping DB init: no TALK2DOM_DB_URI set.")
        return
    Base.metadata.create_all(bind=engine)
    seed_local_data()
