from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from talk2dom.db.session import get_db
from talk2dom.db.models import User
from talk2dom.api.auth.google_oauth import oauth
from talk2dom.api.deps import handle_pending_invites

router = APIRouter(prefix="/google", tags=["auth"])  # 区分为 Google OAuth 专用路径


@router.get("/login")
async def auth_google_login(request: Request):
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token["userinfo"]

    # 保存到数据库（如果不存在则插入）
    user = await User.get_or_create_google_user(db, user_info)

    # 设置 session
    request.session["user"] = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": "google",
    }
    handle_pending_invites(db, user)
    return RedirectResponse(url="/")
