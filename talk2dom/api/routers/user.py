from fastapi import APIRouter, Depends, Request, Body, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from talk2dom.db.models import User, APIKey
from talk2dom.db.session import get_db
from talk2dom.api.deps import get_current_user
from talk2dom.api.utils.token import confirm_email_token, generate_email_token
import secrets
import os

from loguru import logger

router = APIRouter()

templates = Jinja2Templates(directory="talk2dom/templates")
UI_DOMAIN = os.getenv("UI_DOMAIN", "http://localhost:3000")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "plan": user.plan,
        "one_time_credits": user.one_time_credits,
        "subscription_credits": user.subscription_credits,
        "subscription_status": user.subscription_status,
        "subscription_end_date": user.subscription_end_date,
        "is_active": user.is_active,
    }


@router.post("/api-keys")
def create_api_key(
    name: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()
    if len(keys) >= 20:
        raise HTTPException(
            status_code=400, detail="Too many keys, please contact our support"
        )
    key_value = secrets.token_hex(32)
    api_key = APIKey(user_id=current_user.id, key=key_value, name=name)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {
        "api_key": key_value,
        "id": api_key.id,
        "name": api_key.name,
        "created_at": api_key.created_at,
    }


@router.get("/api-keys")
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    keys = (
        db.query(APIKey)
        .filter(APIKey.user_id == current_user.id)
        .order_by(APIKey.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return [
        {
            "id": k.id,
            "name": k.name,
            "key": k.key,
            "created_at": k.created_at,
            "is_active": k.is_active,
        }
        for k in keys
    ]


@router.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = (
        db.query(APIKey)
        .filter(APIKey.id == key_id, APIKey.user_id == current_user.id)
        .first()
    )
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    db.delete(key)
    db.commit()
    return {"detail": "API key deleted"}


@router.get("/verify-email")
def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    email = confirm_email_token(token)
    if not email:
        return templates.TemplateResponse(
            "verify_failed.html",
            {
                "request": request,
                "login_url": f"{UI_DOMAIN}/login",
                "message": "The email verification link is invalid or has expired. Please try again.",
            },
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse(
            "verify_failed.html",
            {
                "request": request,
                "login_url": f"{UI_DOMAIN}/login",
                "message": "The account does not exist. Please try again.",
            },
        )

    if user.is_active:
        return templates.TemplateResponse(
            "verify_success.html",
            {
                "request": request,
                "login_url": f"{UI_DOMAIN}/login",
                "message": "Account already verified.",
            },
        )

    user.is_active = True
    db.commit()

    return templates.TemplateResponse(
        "verify_success.html",
        {
            "request": request,
            "login_url": f"{UI_DOMAIN}/login",
            "message": "Your email has been successfully verified. You can now log in to your account.",
        },
    )


@router.post("/resend-verify-email")
def resend_verify_email(request: Request, user: User = Depends(get_current_user)):
    token = generate_email_token(user.email)
    base_url = str(request.base_url).rstrip("/")
    verify_url = f"{base_url}/api/v1/user/verify-email?token={token}"
    # send_verification_email(to_email=data.email, verify_url=verify_url)
    logger.info(f"Sending verification email to {verify_url}")
    return {"message": "Verification email sent."}


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url=os.environ.get("UI_DOMAIN"))
