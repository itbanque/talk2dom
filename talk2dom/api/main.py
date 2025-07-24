import os
from fastapi import FastAPI
from talk2dom.db.init import init_db
from talk2dom.api.routers.auth import google  # 👈 所有 OAuth 路由集中注册
from talk2dom.api.routers import user, inference
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="Talk2DOM API")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY"))

init_db()

app.include_router(google.router, prefix="/auth", tags=["auth"])
app.include_router(user.router, prefix="/user", tags=["user"])
app.include_router(inference.router, prefix="/inference", tags=["inference"])
