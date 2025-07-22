from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from loguru import logger

DB_URI = os.environ.get("TAK2DOM_DB_URI", None)
SessionLocal = None
engine = None

if not DB_URI:
    logger.warning(
        "TAK2DOM_DB_URI not set, running in no-cache mode (no database connection). It will bring extra costs."
    )

if DB_URI:
    engine = create_engine(DB_URI, echo=False)
    SessionLocal = sessionmaker(bind=engine)
