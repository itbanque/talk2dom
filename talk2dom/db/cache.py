from talk2dom.db.models import UILocatorCache
from talk2dom.db.session import SessionLocal
import hashlib
from loguru import logger


def compute_locator_id(instruction: str, html: str) -> str:
    raw = (instruction.strip() + html.strip()).encode("utf-8")
    uuid = hashlib.sha256(raw).hexdigest()
    logger.debug(
        f"Computing locator ID for instruction: {instruction[:50]}... and HTML length: {len(html)}, UUID: {uuid}"
    )
    return uuid


def get_cached_locator(instruction: str, html: str):

    if SessionLocal is None:
        return None, None

    locator_id = compute_locator_id(instruction, html)
    session = SessionLocal()

    try:
        row = session.query(UILocatorCache).filter_by(id=locator_id).first()
        if row:
            logger.debug(f"Cache hit for locator ID: {locator_id}")
        else:
            logger.debug(f"Cache miss for locator ID: {locator_id}")
        return (row.selector_type, row.selector_value) if row else (None, None)
    finally:
        session.close()


def save_locator(instruction: str, html: str, selector_type: str, selector_value: str):
    if SessionLocal is None:
        return None
    locator_id = compute_locator_id(instruction, html)
    session = SessionLocal()
    try:
        record = UILocatorCache(
            id=locator_id,
            user_instruction=instruction,
            html=html,
            selector_type=selector_type,
            selector_value=selector_value,
        )
        session.add(record)
        session.commit()
        logger.debug(f"Saved locator with ID: {locator_id}")
    except Exception as e:
        session.rollback()  # Rollback on any error
        logger.error(f"Error saving locator: {e}")
    finally:
        session.close()
