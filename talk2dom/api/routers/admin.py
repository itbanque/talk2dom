import json
import os
import secrets
import uuid
from collections import Counter
from datetime import datetime, timedelta
from html import escape as html_escape
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session

from talk2dom.api.deps import handle_pending_invites
from talk2dom.api.limiter import limiter
from talk2dom.api.utils import hash_helper
from talk2dom.db.cache import compute_locator_id, invalidate_locator_cache
from talk2dom.db.models import (
    APIKey,
    APIUsage,
    HTML,
    Project,
    ProjectInvite,
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
    error: str = Query(default=""),
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
            "csrf_token": _csrf_token(request),
            "error": error,
        },
    )


@router.post("/create-user")
async def admin_create_user(
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))

    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    name = form.get("name", "").strip() or None
    plan = form.get("plan", "free")
    if plan not in PLAN_CHOICES:
        plan = "free"

    if not email or "@" not in email:
        return RedirectResponse(
            url="/admin/?error=Valid+email+required", status_code=303
        )
    if len(password) < 8:
        return RedirectResponse(
            url="/admin/?error=Password+must+be+at+least+8+characters", status_code=303
        )
    if db.query(User).filter(User.email == email).first():
        return RedirectResponse(
            url="/admin/?error=Email+already+registered", status_code=303
        )

    # 与邮箱注册同一套字段;admin 创建的账户直接激活,跳过邮箱验证
    user = User(
        email=email,
        provider_user_id=f"local:{email}",
        hashed_password=hash_helper.hash_password(password),
        provider="credentials",
        name=name,
        plan=plan,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    handle_pending_invites(db, user)
    logger.info(f"[admin:{actor}] created user {email} (plan={plan})")
    return RedirectResponse(url=f"/admin/users/{user.id}?saved=1", status_code=303)


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


def _nice_ceiling(v: int) -> int:
    if v <= 0:
        return 1
    magnitude = 1
    while True:
        for step in (1, 2, 5):
            if step * magnitude >= v:
                return step * magnitude
        magnitude *= 10


def _usage_chart_svg(daily: list) -> str:
    """Render daily call counts as a column chart (inline SVG, light surface)."""
    W, H = 920, 220
    left, right, top, bottom = 44, 10, 18, 26
    plot_w, plot_h = W - left - right, H - top - bottom
    n = len(daily)
    band = plot_w / n
    bar_w = min(24.0, band - 4)
    max_val = max((v for _, v in daily), default=0)
    nice = _nice_ceiling(max_val)

    parts = [
        f'<svg class="usage-chart" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Daily API calls, last {n} days" '
        'style="width:100%;height:auto;display:block;">',
        "<style>"
        ".usage-chart .slot .bar{fill:#2a78d6;}"
        ".usage-chart .slot:hover .bar{fill:#1c5cab;}"
        ".usage-chart .slot .band{fill:transparent;}"
        ".usage-chart .slot:hover .band{fill:rgba(42,120,214,0.08);}"
        ".usage-chart text{font:11px system-ui,sans-serif;fill:#898781;"
        "font-variant-numeric:tabular-nums;}"
        "</style>",
    ]

    # hairline gridlines + y ticks at clean numbers (skip a non-integer midpoint)
    ticks = [0, nice] if nice % 2 else [0, nice // 2, nice]
    for val in ticks:
        y = top + plot_h - plot_h * val / nice
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" '
            f'stroke="{"#c3c2b7" if val == 0 else "#e1e0d9"}" stroke-width="1"/>'
            f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end">{val}</text>'
        )

    peak_idx = max(range(n), key=lambda i: daily[i][1], default=0) if max_val else None
    for i, (day, val) in enumerate(daily):
        x = left + i * band
        label = f"{day.strftime('%b %d').replace(' 0', ' ')} · {val} calls"
        parts.append(f'<g class="slot" data-label="{html_escape(label, quote=True)}">')
        if val > 0:
            h = plot_h * val / nice
            bx = x + (band - bar_w) / 2
            by = top + plot_h - h
            r = min(4.0, h, bar_w / 2)
            parts.append(
                f'<path class="bar" d="M{bx:.1f},{by + h:.1f} V{by + r:.1f} '
                f"Q{bx:.1f},{by:.1f} {bx + r:.1f},{by:.1f} H{bx + bar_w - r:.1f} "
                f'Q{bx + bar_w:.1f},{by:.1f} {bx + bar_w:.1f},{by + r:.1f} V{by + h:.1f} Z"/>'
            )
            if i == peak_idx:
                parts.append(
                    f'<text x="{bx + bar_w / 2:.1f}" y="{by - 5:.1f}" '
                    f'text-anchor="middle" style="fill:#52514e;">{val}</text>'
                )
        parts.append(
            f'<rect class="band" x="{x:.1f}" y="{top}" width="{band:.1f}" '
            f'height="{plot_h}"><title>{html_escape(label)}</title></rect></g>'
        )

    for i in range(0, n, 7):
        x = left + i * band + band / 2
        day_label = daily[i][0].strftime("%b %d").replace(" 0", " ")
        parts.append(
            f'<text x="{x:.1f}" y="{H - 8}" text-anchor="middle">{day_label}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


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


def _get_cache_or_404(db: Session, cache_id: str) -> UILocatorCache:
    row = db.query(UILocatorCache).filter(UILocatorCache.id == cache_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Locator not found")
    return row


def _get_usage_or_404(db: Session, usage_id: str) -> APIUsage:
    try:
        uid = uuid.UUID(usage_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Usage record not found")
    usage = db.query(APIUsage).filter(APIUsage.id == uid).first()
    if not usage:
        raise HTTPException(status_code=404, detail="Usage record not found")
    return usage


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


def _get_user_or_404(db: Session, user_id: str) -> User:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="User not found")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _fmt_action(action_type: str, action_value: str) -> str:
    if not action_type:
        return ""
    return f"{action_type}: {action_value}" if action_value else action_type


# meta 来源最多回看这么多条 usage;更早的重复定位基本都已沉淀为 cache 条目
LOCATED_USAGE_SCAN_LIMIT = 1000


def _located_elements(
    db: Session, user: User, project_filter: str, project_by_id: dict
):
    """该用户定位过的元素:项目缓存条目 ∪ usage meta_data(含 playground),按 locator 指纹去重."""
    rows = []

    if project_filter == "none":
        cache_project_ids = []  # playground 调用不产生按项目归属的缓存
    elif project_filter:
        cache_project_ids = [pid for pid in project_by_id if str(pid) == project_filter]
    else:
        cache_project_ids = list(project_by_id)

    if cache_project_ids:
        for c in (
            db.query(UILocatorCache)
            .filter(UILocatorCache.project_id.in_(cache_project_ids))
            .all()
        ):
            action_type, _, action_value = (c.action or "").partition(":")
            rows.append(
                {
                    "key": c.id,
                    "time": c.updated_at,
                    "instruction": c.user_instruction,
                    "url": c.url,
                    "selector_type": c.selector_type,
                    "selector_value": c.selector_value,
                    "action": _fmt_action(action_type, action_value),
                    "project": project_by_id.get(c.project_id, "—"),
                    "snapshot_url": f"/admin/cache/{c.id}/snapshot",
                    "delete_url": f"/admin/cache/{c.id}/delete",
                }
            )

    usage_query = db.query(APIUsage).filter(
        APIUsage.user_id == user.id, APIUsage.meta_data.isnot(None)
    )
    if project_filter == "none":
        usage_query = usage_query.filter(APIUsage.project_id.is_(None))
    elif project_filter:
        try:
            usage_query = usage_query.filter(
                APIUsage.project_id == uuid.UUID(project_filter)
            )
        except ValueError:
            usage_query = usage_query.filter(false())
    recent = (
        usage_query.order_by(APIUsage.request_time.desc())
        .limit(LOCATED_USAGE_SCAN_LIMIT)
        .all()
    )

    seen = {r["key"] for r in rows}
    for u in recent:
        m = u.meta_data or {}
        if not m.get("selector_value"):
            continue
        key = compute_locator_id(
            m.get("user_instruction", ""),
            m.get("html_id", ""),
            m.get("url"),
            str(u.project_id) if u.project_id else "",
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "key": key,
                "time": u.request_time,
                "instruction": m.get("user_instruction", ""),
                "url": m.get("url", ""),
                "selector_type": m.get("selector_type", ""),
                "selector_value": m.get("selector_value", ""),
                "action": _fmt_action(
                    m.get("action_type", ""), m.get("action_value", "")
                ),
                "project": project_by_id.get(u.project_id)
                or ("Playground" if not u.project_id else str(u.project_id)[:8]),
                "snapshot_url": f"/admin/usage/{u.id}/snapshot",
                "delete_url": f"/admin/usage/{u.id}/delete",
            }
        )

    rows.sort(key=lambda r: r["time"] or datetime.min, reverse=True)
    return rows


@router.get("/users/{user_id}")
def edit_user_page(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
    saved: int = Query(default=0),
    error: str = Query(default=""),
    cpage: int = Query(default=1, ge=1),
    project: str = Query(default=""),
):
    user = _get_user_or_404(db, user_id)
    usage_query = db.query(APIUsage).filter(APIUsage.user_id == user.id)

    # 最近 30 天按日聚合(在 Python 里做,SQLite/Postgres 通用)
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=29)
    times = usage_query.with_entities(APIUsage.request_time).filter(
        APIUsage.request_time >= datetime.combine(start_date, datetime.min.time())
    )
    day_counts = Counter(t[0].date() for t in times if t[0])
    daily = [
        (
            start_date + timedelta(days=i),
            day_counts.get(start_date + timedelta(days=i), 0),
        )
        for i in range(30)
    ]

    stats = {
        "projects_owned": db.query(func.count(Project.id))
        .filter(Project.owner_id == user.id)
        .scalar(),
        "api_keys": db.query(func.count(APIKey.id))
        .filter(APIKey.user_id == user.id)
        .scalar(),
        "usage_total": usage_query.count(),
        "usage_30d": sum(day_counts.values()),
    }

    # 用户所属项目(owner + member),用于项目筛选下拉和缓存条目归属
    member_ids = [
        row[0]
        for row in db.query(ProjectMembership.project_id)
        .filter(ProjectMembership.user_id == user.id)
        .all()
    ]
    projects = (
        db.query(Project)
        .filter(or_(Project.owner_id == user.id, Project.id.in_(member_ids)))
        .all()
    )
    project_by_id = {p.id: p.name for p in projects}

    api_keys = (
        db.query(APIKey)
        .filter(APIKey.user_id == user.id)
        .order_by(APIKey.created_at.desc())
        .all()
    )
    members_by_project = {}
    invites_by_project = {}
    if project_by_id:
        member_rows = (
            db.query(ProjectMembership, User)
            .join(User, ProjectMembership.user_id == User.id)
            .filter(ProjectMembership.project_id.in_(project_by_id))
            .all()
        )
        for membership, member in member_rows:
            members_by_project.setdefault(membership.project_id, []).append(
                {"id": membership.id, "email": member.email, "role": membership.role}
            )
        for invite in (
            db.query(ProjectInvite)
            .filter(
                ProjectInvite.project_id.in_(project_by_id),
                ProjectInvite.accepted.is_(False),
            )
            .all()
        ):
            invites_by_project.setdefault(invite.project_id, []).append(
                {"id": invite.id, "email": invite.email}
            )

    located = _located_elements(db, user, project, project_by_id)
    located_total = len(located)
    located_page = located[(cpage - 1) * USAGE_PAGE_SIZE : cpage * USAGE_PAGE_SIZE]

    return templates.TemplateResponse(
        "admin/user_edit.html",
        {
            "request": request,
            "actor": actor,
            "user": user,
            "stats": stats,
            "usage_chart": _usage_chart_svg(daily),
            "located": located_page,
            "located_total": located_total,
            "projects": projects,
            "api_keys": api_keys,
            "members_by_project": members_by_project,
            "invites_by_project": invites_by_project,
            "project_filter": project,
            "cpage": cpage,
            "located_has_next": cpage * USAGE_PAGE_SIZE < located_total,
            "plan_choices": PLAN_CHOICES,
            "csrf_token": _csrf_token(request),
            "saved": saved,
            "error": error,
        },
    )


@router.post("/users/{user_id}/projects")
async def admin_create_project(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    user = _get_user_or_404(db, user_id)
    name = form.get("name", "").strip()
    if not name:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=Project+name+required", status_code=303
        )
    project = Project(name=name, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    db.add(ProjectMembership(user_id=user.id, project_id=project.id, role="owner"))
    db.commit()
    logger.info(
        f"[admin:{actor}] created project {project.id} ({name}) for user {user.email}"
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?saved=1", status_code=303)


@router.post("/users/{user_id}/api-keys")
async def admin_create_api_key(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    user = _get_user_or_404(db, user_id)
    name = form.get("name", "").strip() or None
    api_key = APIKey(user_id=user.id, key=secrets.token_hex(32), name=name)
    db.add(api_key)
    db.commit()
    logger.info(
        f"[admin:{actor}] created API key {api_key.id} ({name}) for user {user.email}"
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?saved=1", status_code=303)


@router.post("/users/{user_id}/invite")
async def admin_invite_member(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    user = _get_user_or_404(db, user_id)

    email = form.get("email", "").strip().lower()
    if not email or "@" not in email:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=Valid+email+required", status_code=303
        )
    try:
        project_id = uuid.UUID(form.get("project_id", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    already_member = (
        db.query(ProjectMembership)
        .filter(
            ProjectMembership.project_id == project_id,
            ProjectMembership.user.has(email=email),
        )
        .first()
    )
    if already_member:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=User+is+already+a+member",
            status_code=303,
        )
    pending = (
        db.query(ProjectInvite)
        .filter(
            ProjectInvite.project_id == project_id,
            ProjectInvite.email == email,
            ProjectInvite.accepted.is_(False),
        )
        .first()
    )
    if pending:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?error=User+already+invited", status_code=303
        )

    invite = ProjectInvite(
        project_id=project_id, email=email, invited_by_user_id=user.id
    )
    invitee = db.query(User).filter(User.email == email).first()
    if invitee:
        # 已注册用户直接加入,不必等下次登录
        db.add(
            ProjectMembership(user_id=invitee.id, project_id=project_id, role="member")
        )
        invite.accepted = True
        invite.invited_user_id = invitee.id
    db.add(invite)
    db.commit()
    logger.info(
        f"[admin:{actor}] invited {email} to project {project_id} "
        f"({'joined directly' if invitee else 'pending signup'})"
    )
    return RedirectResponse(url=f"/admin/users/{user_id}?saved=1", status_code=303)


@router.post("/memberships/{membership_id}/delete")
async def admin_remove_member(
    membership_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    back = form.get("user_id", "")
    try:
        mid = uuid.UUID(membership_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership = db.query(ProjectMembership).filter(ProjectMembership.id == mid).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    project = db.query(Project).filter(Project.id == membership.project_id).first()
    if project and membership.user_id == project.owner_id:
        return RedirectResponse(
            url=f"/admin/users/{back}?error=Owner+cannot+be+removed", status_code=303
        )
    db.query(ProjectInvite).filter_by(
        invited_user_id=membership.user_id, project_id=membership.project_id
    ).delete()
    db.delete(membership)
    db.commit()
    logger.info(
        f"[admin:{actor}] removed member {membership.user_id} "
        f"from project {membership.project_id}"
    )
    return RedirectResponse(url=f"/admin/users/{back}?saved=1", status_code=303)


@router.post("/invites/{invite_id}/delete")
async def admin_revoke_invite(
    invite_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    back = form.get("user_id", "")
    try:
        iid = uuid.UUID(invite_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite = db.query(ProjectInvite).filter(ProjectInvite.id == iid).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    db.delete(invite)
    db.commit()
    logger.info(f"[admin:{actor}] revoked invite {invite_id} ({invite.email})")
    return RedirectResponse(url=f"/admin/users/{back}?saved=1", status_code=303)


@router.post("/api-keys/{key_id}/delete")
async def admin_delete_api_key(
    key_id: str,
    request: Request,
    db: Session = Depends(get_db),
    actor: str = Depends(require_admin),
):
    form = await _parse_form(request)
    _check_csrf(request, form.get("csrf_token", ""))
    back = form.get("user_id", "")
    try:
        kid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="API key not found")
    key = db.query(APIKey).filter(APIKey.id == kid).first()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
    logger.info(f"[admin:{actor}] deleted API key {key_id} of user {key.user_id}")
    return RedirectResponse(url=f"/admin/users/{back}?saved=1", status_code=303)


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
