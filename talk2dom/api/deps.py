# talk2dom/api/deps.py
import time
from datetime import datetime
from functools import wraps

from fastapi import Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.testing.suite.test_reflection import metadata

from talk2dom.db.session import get_db
from talk2dom.db.models import User, APIUsage, APIKey

from loguru import logger


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

            req = kwargs.get("req")
            request = kwargs.get("request")
            db: Session = kwargs.get("db")
            api_key_id = kwargs.get("api_key_id")

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
                endpoint=str(req.url),
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
            db.commit()

            if status_code == 500:
                return JSONResponse(content=response_data, status_code=500)
            return response_data

        return wrapper

    return decorator
