import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from talk2dom.db.session import get_db
from talk2dom.db.models import User
from talk2dom.api.auth.github_oauth import oauth
from talk2dom.api.deps import handle_pending_invites

from loguru import logger

router = APIRouter(prefix="/github")


@router.get("/login")
async def auth_github_login(request: Request):
    redirect_uri = request.url_for("auth_github_callback")
    request.app.state._oauth_github_last_redirect = str(redirect_uri)
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def auth_github_callback(request: Request, db: AsyncSession = Depends(get_db)):
    token = await oauth.github.authorize_access_token(request)
    # Fetch basic user profile
    user_resp = await oauth.github.get("user", token=token)
    user_info = user_resp.json()

    # GitHub's /user often lacks email; fetch from /user/emails
    primary_email = None
    try:
        emails_resp = await oauth.github.get("user/emails", token=token)
        if emails_resp.status_code == 200:
            emails = emails_resp.json()
            # Prefer primary & verified
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    primary_email = e.get("email")
                    break
            # Fallback to any verified email
            if not primary_email:
                for e in emails:
                    if e.get("verified"):
                        primary_email = e.get("email")
                        break
    except Exception as exc:
        logger.warning(f"Failed to fetch GitHub emails: {exc}")

    if not primary_email:
        # As a last resort, some accounts expose email on /user
        primary_email = user_info.get("email")

    if not primary_email:
        raise HTTPException(
            status_code=400,
            detail=(
                "No verified email available from GitHub. Please verify your email on GitHub and try again."
            ),
        )

    # Create or fetch local user with resolved email
    user = await User.get_or_create_github_user(db, user_info, email=primary_email)

    request.session["user"] = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": "github",
    }
    handle_pending_invites(db, user)
    response = RedirectResponse(url=f"{os.environ.get('UI_DOMAIN')}/projects")
    return response
