import os
from fastapi import FastAPI
from talk2dom.db.init import init_db
from talk2dom.api.routers.auth import google, email
from talk2dom.api.routers import user, inference, project, subscription, webhook

from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
from talk2dom.api.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="Talk2DOM API")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY"))
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://talk2dom-ui-kz5t.vercel.app/"],
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
