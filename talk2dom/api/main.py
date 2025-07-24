import os
from fastapi import FastAPI
from talk2dom.db.init import init_db
from talk2dom.api.routers.auth import google
from talk2dom.api.routers import user, inference, project

from starlette.middleware.sessions import SessionMiddleware
from talk2dom.api.limiter import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from dotenv import load_dotenv


load_dotenv()

app = FastAPI(title="Talk2DOM API")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY"))
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

init_db()

app.include_router(google.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(inference.router, prefix="/inference", tags=["inference"])

app.include_router(project.router, prefix="/project", tags=["project"])
