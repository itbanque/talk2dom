import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from talk2dom.api.limiter import limiter
from talk2dom.db.models import APIKey, APIUsage, Project, User
from talk2dom.db.session import get_db

from loguru import logger

router = APIRouter()
templates = Jinja2Templates(directory="talk2dom/templates")

PLAN_CHOICES = ["free", "developer", "pro", "enterprise"]
PAGE_SIZE = 50


async def _parse_form(request: Request) -> dict:
    # 手动解析 urlencoded 表单,避免引入 python-multipart 依赖
    body = (await request.body()).decode("utf-8", errors="replace")
    return {k: v[0] for k, v in parse_qs(body).items()}


def _admin_token() -> Optional[str]:
    # 不设置 ADMIN_TOKEN 即可彻底关闭 token 登录入口
    token = os.environ.get("ADMIN_TOKEN", "").strip()
    return token or None


def _login_redirect() -> HTTPException:
    return HTTPException(status_code=303, headers={"Location": "/admin/login"})


def require_admin(request: Request, db: Session = Depends(get_db)) -> str:
    """Return the acting admin identity ('token' or the admin user's email)."""
    if request.session.get("admin_via_token"):
        if _admin_token() is None:
            request.session.pop("admin_via_token", None)
            raise _login_redirect()
        return "token"

    session_user = request.session.get("user")
    if session_user:
        try:
            uid = uuid.UUID(str(session_user.get("id", "")))
        except ValueError:
            uid = None
        if uid is not None:
            user = db.query(User).filter(User.id == uid).first()
            if user is not None and user.is_admin:
                return user.email

    raise _login_redirect()


def _csrf_token(request: Request) -> str:
    token = request.session.get("admin_csrf")
    if not token:
        token = secrets.token_hex(16)
        request.session["admin_csrf"] = token
    return token


def _check_csrf(request: Request, csrf_token: str) -> None:
    expected = request.session.get("admin_csrf")
    if not expected or not secrets.compare_digest(expected, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "admin/login.html",
        {
            "request": request,
            "token_login_enabled": _admin_token() is not None,
            "error": None,
        },
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request):
    form = await _parse_form(request)
    token = form.get("token", "")
    expected = _admin_token()
    if expected is None or not secrets.compare_digest(expected, token.strip()):
        logger.warning("Admin token login failed")
        return templates.TemplateResponse(
            "admin/login.html",
            {
                "request": request,
                "token_login_enabled": expected is not None,
                "error": "Invalid token.",
            },
            status_code=401,
        )
    request.session["admin_via_token"] = True
    logger.info("Admin logged in via token")
    return RedirectResponse(url="/admin/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.pop("admin_via_token", None)
    request.session.pop("admin_csrf", None)
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("/")
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
    q: str = Query(default=""),
    plan: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(User)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(pattern), User.name.ilike(pattern)))
    if plan:
        query = query.filter(User.plan == plan)

    total = query.count()
    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    plan_counts = dict(
        db.query(User.plan, func.count(User.id)).group_by(User.plan).all()
    )

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "actor": actor,
            "users": users,
            "q": q,
            "plan": plan,
            "page": page,
            "has_next": page * PAGE_SIZE < total,
            "total": total,
            "plan_counts": plan_counts,
            "plan_choices": PLAN_CHOICES,
        },
    )


def _get_user_or_404(db: Session, user_id: str) -> User:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{user_id}")
def edit_user_page(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
    saved: int = Query(default=0),
    error: str = Query(default=""),
):
    user = _get_user_or_404(db, user_id)
    month_ago = datetime.utcnow() - timedelta(days=30)
    stats = {
        "projects_owned": db.query(func.count(Project.id))
        .filter(Project.owner_id == user.id)
        .scalar(),
        "api_keys": db.query(func.count(APIKey.id))
        .filter(APIKey.user_id == user.id)
        .scalar(),
        "usage_30d": db.query(func.count(APIUsage.id))
        .filter(APIUsage.user_id == user.id, APIUsage.request_time >= month_ago)
        .scalar(),
    }
    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "actor": actor,
            "user": user,
            "stats": stats,
            "plan_choices": PLAN_CHOICES,
            "csrf_token": _csrf_token(request),
            "saved": saved,
            "error": error,
        },
    )


@router.post("/users/{user_id}")
async def update_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    user = _get_user_or_404(db, user_id)

    plan = form.get("plan", "")
    if plan not in PLAN_CHOICES:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=Invalid+plan", status_code=303
        )
    try:
        subscription_credits = int(form.get("subscription_credits", ""))
        one_time_credits = int(form.get("one_time_credits", ""))
    except (TypeError, ValueError):
        subscription_credits = one_time_credits = -1
    if subscription_credits < 0 or one_time_credits < 0:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=Credits+must+be+a+number+%3E%3D+0",
            status_code=303,
        )
    is_active = form.get("is_active")
    is_admin = form.get("is_admin")

    before = (
        f"plan={user.plan}, sub_credits={user.subscription_credits}, "
        f"one_time_credits={user.one_time_credits}, is_active={user.is_active}, "
        f"is_admin={user.is_admin}"
    )
    user.plan = plan
    user.subscription_credits = subscription_credits
    user.one_time_credits = one_time_credits
    user.is_active = is_active is not None
    user.is_admin = is_admin is not None
    db.commit()

    logger.info(
        f"[admin:{actor}] updated user {user.email}: ({before}) -> "
        f"(plan={user.plan}, sub_credits={user.subscription_credits}, "
        f"one_time_credits={user.one_time_credits}, is_active={user.is_active}, "
        f"is_admin={user.is_admin})"
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?saved=1", status_code=303)
