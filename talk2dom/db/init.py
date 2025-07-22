from talk2dom.db.models import Base
from talk2dom.db.session import engine, SessionLocal
from loguru import logger


def init_db():
    if SessionLocal is None:
        logger.warning("Skipping DB init: no TAK2DOM_DB_URI set.")
        return
    Base.metadata.create_all(bind=engine)
