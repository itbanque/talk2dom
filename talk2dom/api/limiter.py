# talk2dom/api/limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def get_api_key_for_limit(request: Request):
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:]
    return "anonymous"  # fallback


limiter = Limiter(key_func=get_remote_address)
