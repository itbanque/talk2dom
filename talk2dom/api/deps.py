# talk2dom/api/deps.py
from datetime import datetime
from functools import wraps

from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from talk2dom.db.session import get_db
from talk2dom.db.models import User, APIUsage, APIKey
from talk2dom.api.limiter import limiter
from talk2dom.db.models import ProjectInvite, ProjectMembership, Project
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException, Depends
from uuid import UUID

from loguru import logger


num_limit = {
    "free": 1,
    "developer": 2,
    "pro": 10,
    "enterprise": float("inf"),
}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user.get("id", "")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def get_api_key_user(
    request: Request,
    db: Session = Depends(get_db),
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid API Key")

    api_key = auth_header.split(" ")[1]

    user = db.query(User).filter(User.api_keys.any(key=api_key)).first()
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    return user


def get_api_key_id(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid API Key")

    api_key = auth_header.removeprefix("Bearer ").strip()

    key_obj = db.query(APIKey).filter(APIKey.key == api_key).first()
    if not key_obj:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    return str(key_obj.id)


def track_api_usage():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            db: Session = kwargs.get("db")
            api_key_id = kwargs.get("api_key_id")
            user = kwargs.get("user")
            project_id = kwargs.get("project_id")

            if not has_project_access(db, user.id, project_id):
                logger.error(
                    f"User {user.id} does not have access to project {project_id}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"The API Key can't access the project: {project_id}",
                )

            project_owner = get_project_owner(db, project_id)
            if (
                int(project_owner.subscription_credits + project_owner.one_time_credits)
                <= 0
            ):
                raise HTTPException(status_code=402, detail="Not enough credits")

            num_limit = {
                "free": 1,
                "developer": 2,
                "pro": 10,
                "enterprise": float("inf"),
            }
            members = (
                db.query(ProjectMembership)
                .filter(ProjectMembership.project_id == project_id)
                .all()
            )
            if len(members) > num_limit.get(project_owner.plan, 0):
                raise HTTPException(
                    status_code=400,
                    detail="Member limit exceeded for your plan. Please upgrade your plan or remove member to continue.",
                )

            start = datetime.utcnow()
            try:
                response_data = func(*args, **kwargs)
                status_code = 200
            except Exception as e:
                response_data = {"error": str(e)}
                status_code = 500

            end = datetime.utcnow()
            duration_ms = int((end - start).total_seconds() * 1000)

            input_tokens = getattr(request.state, "input_tokens", None)
            output_tokens = getattr(request.state, "output_tokens", None)
            metadata = getattr(request.state, "usage_metadata", {})

            usage = APIUsage(
                api_key_id=api_key_id,
                user_id=user.id,
                project_id=project_id,
                endpoint=str(request.url.path),
                request_time=start,
                response_time=end,
                duration_ms=duration_ms,
                status_code=status_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                meta_data=metadata,
                call_llm=getattr(request.state, "call_llm", False),
            )
            db.add(usage)

            if status_code == 200:
                consume_credit(db, project_owner, amount=1)

            db.commit()

            if status_code == 500:
                return JSONResponse(content=response_data, status_code=500)
            return response_data

        return wrapper

    return decorator


def playground_track_api_usage():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            db: Session = kwargs.get("db")
            request = kwargs.get("request")
            user = kwargs.get("user")

            if (int(user.subscription_credits) + int(user.one_time_credits)) <= 0:
                raise HTTPException(status_code=403, detail="Not enough credits")

            start = datetime.utcnow()
            try:
                response_data = func(*args, **kwargs)
                status_code = 200
            except Exception as e:
                response_data = {"error": str(e)}
                status_code = 500

            end = datetime.utcnow()
            duration_ms = int((end - start).total_seconds() * 1000)

            input_tokens = getattr(request.state, "input_tokens", None)
            output_tokens = getattr(request.state, "output_tokens", None)
            metadata = getattr(request.state, "usage_metadata", {})

            usage = APIUsage(
                api_key_id=None,
                user_id=user.id,
                project_id=None,
                endpoint=str(request.url.path),
                request_time=start,
                response_time=end,
                duration_ms=duration_ms,
                status_code=status_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                meta_data=metadata,
                call_llm=getattr(request.state, "call_llm", False),
            )
            db.add(usage)

            if status_code == 200:
                consume_credit(db, user, amount=1)

            db.commit()

            if status_code == 500:
                return HTTPException(detail=response_data, status_code=500)
            return response_data

        return wrapper

    return decorator


def rate_limiter_by_user(plan_rates: dict = None):
    if plan_rates is None:
        plan_rates = {
            "free": "5/minute",
            "starter": "60/minute",
            "pro": "200/minute",
            "business": "1000/minute",
            "enterprise": "5000/minute",
        }

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if not user:
                raise Exception("Missing user for rate limiting.")

            plan = getattr(user, "plan", "free")
            rate = plan_rates.get(plan, "5/minute")
            logger.info(f"⏳ Rate limiting for user {user.id} ({plan}): {rate}")

            def key_func():
                return str(user.id)

            try:
                limit_decorator = limiter.limit(rate)
                return limit_decorator(func)(*args, **kwargs)
            except RateLimitExceeded:
                return JSONResponse(
                    status_code=429, content={"detail": "Rate limit exceeded."}
                )

        return wrapper

    return decorator


def handle_pending_invites(db: Session, user: User):
    invites = db.query(ProjectInvite).filter_by(email=user.email, accepted=False).all()
    logger.info(f"Found {len(invites)} invites for user {user.email}")
    for invite in invites:
        members = (
            db.query(Project)
            .join(ProjectMembership, Project.id == invite.project_id)
            .filter(ProjectMembership.user_id == invite.invited_by_user_id)
            .all()
        )
        owner = db.query(User).filter(User.id == invite.invited_by_user_id).first()

        if len(members) >= num_limit.get(owner.plan, 0):
            logger.warning(
                f"The members of project: {invite.project_id} is already over the limit."
            )
            continue
        db.add(ProjectMembership(user_id=user.id, project_id=invite.project_id))
        invite.accepted = True
        invite.invited_user_id = user.id
    db.commit()


async def get_current_project_id(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    project_id = request.query_params.get("project_id") or request.headers.get(
        "X-Project-ID"
    )
    if not project_id:
        raise HTTPException(status_code=400, detail="Missing project_id")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project_id


def get_project_owner(db: Session, project_id: UUID) -> User:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    owner = db.query(User).filter(User.id == project.owner_id).first()
    return owner


def consume_credit(db: Session, user: User, amount: int = 1):
    if user.subscription_credits >= amount:
        user.subscription_credits -= amount
    elif user.subscription_credits + user.one_time_credits >= amount:
        remaining = amount - user.subscription_credits
        user.subscription_credits = 0
        user.one_time_credits -= remaining
    else:
        raise HTTPException(status_code=400, detail="Credit not enough")


def has_project_access(db: Session, user_id: UUID, project_id: UUID):
    is_owner = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == user_id)
        .first()
    )

    if is_owner:
        return True

    is_member = (
        db.query(ProjectMembership)
        .filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user_id == user_id,
        )
        .first()
    )

    if is_member:
        return True

    return False
