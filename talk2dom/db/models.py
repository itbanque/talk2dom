from sqlalchemy import (
    Column,
    Integer,
    JSON,
    ForeignKey,
    String,
    Text,
    TIMESTAMP,
    func,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from sqlalchemy.orm import Session, relationship


Base = declarative_base()


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)  # 可选：命名这个 key，例如 "for Zapier"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    usages = relationship(
        "APIUsage", back_populates="api_key", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_user_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    name = Column(String, nullable=True)  # ✅ 添加
    picture = Column(String, nullable=True)  # ✅ 添加
    provider = Column(String, nullable=True)  # ✅ 添加，如 'google'
    api_key = Column(String, unique=True)
    stripe_customer_id = Column(String, unique=True)
    stripe_subscription_id = Column(String, unique=True)
    subscription_end_date = Column(DateTime, nullable=True)
    subscription_status = Column(String, nullable=True)
    plan = Column(String, default="free")
    subscription_credits = Column(Integer, default=100)
    one_time_credits = Column(Integer, default=0)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    usages = relationship("APIUsage", back_populates="user")
    api_keys = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    memberships = relationship("ProjectMembership", back_populates="user")

    @classmethod
    async def get_or_create_google_user(cls, db: Session, user_info: dict):
        """检查用户是否存在，若不存在则创建"""
        email = user_info["email"]
        existing_user = db.query(cls).filter_by(email=email).first()
        if existing_user:
            existing_user.last_login = datetime.utcnow()
            db.commit()
            return existing_user

        new_user = cls(
            email=email,
            provider_user_id=user_info["sub"],
            name=user_info.get("name"),
            picture=user_info.get("picture"),
            provider="google",
            is_active=True,
            last_login=datetime.utcnow(),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user


class APIUsage(Base):
    __tablename__ = "api_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    api_key_id = Column(UUID(as_uuid=True), ForeignKey("api_keys.id"), nullable=True)

    endpoint = Column(String, nullable=False)
    request_time = Column(DateTime, default=datetime.utcnow)
    response_time = Column(DateTime)
    duration_ms = Column(Integer)

    status_code = Column(Integer)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    meta_data = Column(JSON, nullable=True)
    call_llm = Column(Boolean, nullable=False, default=False)

    api_key = relationship("APIKey", back_populates="usages")
    user = relationship("User", back_populates="usages")
    project = relationship("Project", back_populates="usages")


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    owner_id = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("ProjectMembership", back_populates="project")
    locator_cache = relationship(
        "UILocatorCache", back_populates="project", cascade="all, delete-orphan"
    )
    usages = relationship("APIUsage", back_populates="project")


class ProjectMembership(Base):
    __tablename__ = "project_memberships"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, ForeignKey("users.id"))
    project_id = Column(UUID, ForeignKey("projects.id"))
    role = Column(String, default="member")  # 可选值: owner, member, viewer

    user = relationship("User", back_populates="memberships")
    project = relationship("Project", back_populates="memberships")


class ProjectInvite(Base):
    __tablename__ = "project_invites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    email = Column(String, nullable=False, index=True)
    invited_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    accepted = Column(Boolean, default=False)

    project = relationship("Project")


class UILocatorCache(Base):
    __tablename__ = "ui_locator_cache"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=False)
    user_instruction = Column(Text, nullable=False)
    html_id = Column(String, ForeignKey("html.id"))
    selector_type = Column(String, nullable=False)
    selector_value = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)

    project = relationship("Project", back_populates="locator_cache")
    html = relationship("HTML", back_populates="locator_cache")


class HTML(Base):
    __tablename__ = "html"

    id = Column(String, primary_key=True)
    url = Column(String, nullable=True)
    backbone = Column(Text, nullable=False)
    row_html = Column(Text, nullable=False)

    locator_cache = relationship(
        "UILocatorCache", back_populates="html", cascade="all, delete-orphan"
    )
