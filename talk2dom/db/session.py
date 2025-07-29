from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import os

DB_URI = os.environ.get("TALK2DOM_DB_URI", None)
SessionLocal = None
engine = None


if DB_URI:
    engine = create_engine(DB_URI, echo=False)
    SessionLocal = sessionmaker(bind=engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
