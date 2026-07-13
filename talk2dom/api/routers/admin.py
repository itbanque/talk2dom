import json
import os
import secrets
import uuid
from datetime import datetime, timedelta
from html import escape as html_escape
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from talk2dom.api.limiter import limiter
from talk2dom.db.cache import invalidate_locator_cache
from talk2dom.db.models import (
    APIKey,
    APIUsage,
    HTML,
    Project,
    ProjectMembership,
    UILocatorCache,
    User,
)
from talk2dom.db.session import get_db

from loguru import logger

router = APIRouter()
templates = Jinja2Templates(directory="talk2dom/templates")

PLAN_CHOICES = ["free", "developer", "pro", "enterprise"]
PAGE_SIZE = 50
USAGE_PAGE_SIZE = 25


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


# 注入到页面快照里的高亮脚本;__TYPE__/__VALUE__ 由 json.dumps 替换
_HIGHLIGHT_SNIPPET = """
<script>
(function () {
  var t = __TYPE__, v = __VALUE__;
  function find() {
    try {
      if (!v) return null;
      if (t === "xpath") {
        return document.evaluate(
          v, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
        ).singleNodeValue;
      }
      if (t === "id") return document.getElementById(v);
      if (t === "class name") return document.querySelector("." + v);
      if (t === "name") return document.querySelector("[name='" + v + "']");
      return document.querySelector(v);
    } catch (e) { return null; }
  }
  function ready() {
    var el = find();
    var banner = document.createElement("div");
    banner.style.cssText =
      "position:fixed;top:0;left:0;right:0;z-index:2147483647;" +
      "padding:6px 12px;font:13px system-ui;color:#fff;";
    if (el) {
      el.style.outline = "3px solid #ef4444";
      el.style.outlineOffset = "2px";
      el.scrollIntoView({block: "center", inline: "center"});
      banner.style.background = "#16a34a";
      banner.textContent = "Element found: " + t + " = " + v;
    } else {
      banner.style.background = "#dc2626";
      banner.textContent = "Element NOT found in snapshot: " + t + " = " + v;
    }
    document.body.appendChild(banner);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready);
  } else {
    ready();
  }
})();
</script>
"""


def _build_snapshot_doc(row_html: str, meta: dict) -> str:
    page_url = meta.get("url") or ""
    base_tag = f'<base href="{html_escape(page_url, quote=True)}">' if page_url else ""
    script = _HIGHLIGHT_SNIPPET.replace(
        "__TYPE__", json.dumps(meta.get("selector_type") or "")
    ).replace("__VALUE__", json.dumps(meta.get("selector_value") or ""))
    return base_tag + row_html + script


def _get_usage_or_404(db: Session, usage_id: str) -> APIUsage:
    try:
        uid = uuid.UUID(usage_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Usage record not found")
    usage = db.query(APIUsage).filter(APIUsage.id == uid).first()
    if not usage:
        raise HTTPException(status_code=404, detail="Usage record not found")
    return usage


def _snapshot_response(db: Session, html_id: Optional[str], meta: dict) -> HTMLResponse:
    # 快照始终以 sandbox 方式返回:即使直接打开 URL,用户提交的 HTML 也无法在 admin 域执行脚本
    headers = {"Content-Security-Policy": "sandbox allow-scripts"}
    html_row = db.query(HTML).filter(HTML.id == html_id).first() if html_id else None
    if not html_row or not html_row.row_html:
        return HTMLResponse(
            "<body style='font-family:system-ui;color:#64748b;display:flex;"
            "align-items:center;justify-content:center;height:100vh;margin:0;'>"
            "No page snapshot available for this call.</body>",
            headers=headers,
        )
    return HTMLResponse(_build_snapshot_doc(html_row.row_html, meta), headers=headers)


@router.get("/usage/{usage_id}/snapshot")
def usage_snapshot(
    usage_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    usage = _get_usage_or_404(db, usage_id)
    meta = usage.meta_data or {}
    return _snapshot_response(db, meta.get("html_id"), meta)


def _get_cache_or_404(db: Session, cache_id: str) -> UILocatorCache:
    row = db.query(UILocatorCache).filter(UILocatorCache.id == cache_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Locator not found")
    return row


@router.get("/cache/{cache_id}/snapshot")
def cache_snapshot(
    cache_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    row = _get_cache_or_404(db, cache_id)
    meta = {
        "url": row.url,
        "selector_type": row.selector_type,
        "selector_value": row.selector_value,
    }
    return _snapshot_response(db, row.html_id, meta)


@router.post("/cache/{cache_id}/delete")
async def delete_cache_entry(
    cache_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    row = _get_cache_or_404(db, cache_id)
    db.delete(row)
    db.commit()
    invalidate_locator_cache(cache_id)
    logger.info(f"[admin:{actor}] deleted locator cache entry {cache_id}")
    try:
        back_user = uuid.UUID(form.get("user_id", ""))
        return RedirectResponse(url=f"/admin/users/{back_user}", status_code=303)
    except ValueError:
        return RedirectResponse(url="/admin/", status_code=303)


@router.post("/usage/{usage_id}/delete")
async def delete_usage(
    usage_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    usage = _get_usage_or_404(db, usage_id)
    user_id = usage.user_id
    db.delete(usage)
    db.commit()
    logger.info(f"[admin:{actor}] deleted usage record {usage_id} of user {user_id}")
    return RedirectResponse(url=f"/admin/users/{user_id}", status_code=303)


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
    upage: int = Query(default=1, ge=1),
    cpage: int = Query(default=1, ge=1),
):
    user = _get_user_or_404(db, user_id)
    month_ago = datetime.utcnow() - timedelta(days=30)
    usage_query = db.query(APIUsage).filter(APIUsage.user_id == user.id)
    stats = {
        "projects_owned": db.query(func.count(Project.id))
        .filter(Project.owner_id == user.id)
        .scalar(),
        "api_keys": db.query(func.count(APIKey.id))
        .filter(APIKey.user_id == user.id)
        .scalar(),
        "usage_total": usage_query.count(),
        "usage_30d": usage_query.filter(APIUsage.request_time >= month_ago).count(),
    }
    usages = (
        usage_query.options(joinedload(APIUsage.project))
        .order_by(APIUsage.request_time.desc())
        .offset((upage - 1) * USAGE_PAGE_SIZE)
        .limit(USAGE_PAGE_SIZE)
        .all()
    )

    # 用户所属项目(owner + member)下缓存的 locator:前端 Detail/Delete 列表就是这份数据
    project_ids = {
        row[0] for row in db.query(Project.id).filter(Project.owner_id == user.id).all()
    } | {
        row[0]
        for row in db.query(ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .all()
    }
    cache_query = db.query(UILocatorCache).filter(
        UILocatorCache.project_id.in_(project_ids)
    )
    cache_total = cache_query.count()
    cache_entries = (
        cache_query.options(joinedload(UILocatorCache.project))
        .order_by(UILocatorCache.updated_at.desc())
        .offset((cpage - 1) * USAGE_PAGE_SIZE)
        .limit(USAGE_PAGE_SIZE)
        .all()
    )

    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "actor": actor,
            "user": user,
            "stats": stats,
            "usages": usages,
            "upage": upage,
            "usage_has_next": upage * USAGE_PAGE_SIZE < stats["usage_total"],
            "cache_entries": cache_entries,
            "cache_total": cache_total,
            "cpage": cpage,
            "cache_has_next": cpage * USAGE_PAGE_SIZE < cache_total,
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
