from talk2dom.db.models import User
from fastapi import Response


def create_session(user: User, response: Response):
    response.set_cookie(
        key="session",
        value=str(user.id),  # 或 JWT token
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
