from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
from loguru import logger
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
        logger.debug("Trying to connect to DB")
        yield db
    finally:
        db.close()
