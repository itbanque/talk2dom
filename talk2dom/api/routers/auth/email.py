from fastapi import APIRouter, Request, Depends, HTTPException, status, Response

from sqlalchemy.orm import Session
from talk2dom.db.models import User
from talk2dom.api.schemas import (
    RegisterRequest,
    LoginRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
)
from talk2dom.api.utils import hash_helper
from talk2dom.api.utils.token import generate_email_token, confirm_email_token
from talk2dom.api.utils.email import send_verification_email, send_password_reset_email

from talk2dom.db.session import get_db
from talk2dom.api.deps import handle_pending_invites
from loguru import logger

from datetime import datetime
import os


router = APIRouter(prefix="/email")


@router.post("/register")
def register_user(
    data: RegisterRequest, request: Request, db: Session = Depends(get_db)
):
    # Basic strength check
    if len(data.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long",
        )
    email = str(data.email).lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    new_user = User(
        email=email,
        provider_user_id=f"local:{email}",
        hashed_password=hash_helper.hash_password(data.password),
        provider="credentials",
        plan="free",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email
    token = generate_email_token(email)
    base_url = str(request.base_url).rstrip("/")
    verify_url = f"{base_url}/api/v1/user/verify-email?token={token}"
    send_verification_email(to_email=email, verify_url=verify_url)
    logger.info(f"Sending verification email to {email}, URL: {verify_url}")
    return {"message": "Registration successful. Please verify your email."}


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or user.provider != "credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email not registered"
        )
    token = generate_email_token(email)
    base_url = str(request.base_url).rstrip("/")
    # Prefer UI domain if configured
    ui_domain = os.environ.get("UI_DOMAIN")
    reset_base = ui_domain.rstrip("/") if ui_domain else base_url
    reset_url = f"{reset_base}/reset-password?token={token}"
    logger.info(f"Sending forgot password email to {email}, URL: {reset_url}")
    send_password_reset_email(to_email=email, reset_url=reset_url)
    logger.info(f"Sent password reset link to {email}")
    return {
        "message": "Password reset link sent to your email",
    }


@router.post("/login")
def login_user(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = str(data.email).lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    if user.provider != "credentials":
        raise HTTPException(status_code=400, detail="This account uses external login")

    if not hash_helper.verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    user.last_login = datetime.utcnow()

    request.session["user"] = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
    }
    # response.set_cookie(
    #     key="session",
    #     value=str(user.id),  # 或 JWT token
    #     httponly=True,
    #     secure=True,
    #     samesite="Lax",
    #     max_age=60 * 60 * 24 * 7,  # 7 days
    # )
    handle_pending_invites(db, user)
    # response = RedirectResponse(url=f"{os.environ.get("UI_DOMAIN")}/projects")
    return {"message": "Login successful"}


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    # Validate token and extract the email
    try:
        email = confirm_email_token(data.token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    user = db.query(User).filter(User.email == email).first()
    if not user or user.provider != "credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token"
        )

    # Basic strength check
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters long",
        )

    # Update password
    user.hashed_password = hash_helper.hash_password(data.new_password)
    db.add(user)
    db.commit()
    logger.info(f"User {user.email} reset password at {datetime.utcnow().isoformat()}Z")
    return {"message": "Password reset successfully"}
