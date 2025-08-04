import os
from talk2dom.db.init import init_db
from talk2dom.api.limiter import limiter
from talk2dom.api.routers.auth import google, email
from talk2dom.api.routers import (
    user,
    inference,
    project,
    subscription,
    webhook,
    sentry,
    status,
    stripe,
)
from talk2dom.api.utils.sentry import init_sentry

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from slowapi.middleware import SlowAPIMiddleware
from dotenv import load_dotenv

load_dotenv()
init_sentry()

app = FastAPI(title="Talk2DOM API")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY"))
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY"),
    same_site="none",
    https_only=True,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("UI_DOMAIN")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

init_db()

app.include_router(google.router, prefix="/api/v1/auth", tags=["auth"])

app.include_router(email.router, prefix="/api/v1/auth", tags=["user"])

app.include_router(user.router, prefix="/api/v1/user", tags=["user"])
app.include_router(inference.router, prefix="/api/v1/inference", tags=["inference"])

app.include_router(project.router, prefix="/api/v1/project", tags=["project"])

app.include_router(
    subscription.router, prefix="/api/v1/subscription", tags=["subscription"]
)

app.include_router(webhook.router, prefix="/api/v1/webhook", tags=["webhook"])

app.include_router(sentry.router, prefix="/api/v1/sentry", tags=["sentry"])

app.include_router(status.router, prefix="/api/v1/status", tags=["status"])

app.include_router(stripe.router, prefix="/api/v1/payment", tags=["stripe"])
