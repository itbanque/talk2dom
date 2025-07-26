from talk2dom.db.models import UILocatorCache
from talk2dom.db.session import SessionLocal
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

import hashlib
from loguru import logger
from typing import Optional


def compute_locator_id(
    instruction: str,
    html: str,
    url: Optional[str] = "",
    project_id: Optional[str] = "",
) -> str:
    raw = (instruction.strip() + url.strip() + project_id.strip()).encode("utf-8")
    uuid = hashlib.sha256(raw).hexdigest()
    logger.debug(
        f"Computing locator ID for instruction: {instruction[:50]}... and source length: {len(html)}, url: {url}, UUID: {uuid}"
    )
    return uuid


def get_cached_locator(
    instruction: str,
    html: str,
    url: Optional[str] = None,
    project_id: Optional[str] = "",
) -> str:
    if SessionLocal is None:
        return None, None

    locator_id = compute_locator_id(instruction, html, url, project_id)
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


def locator_exists(locator_id) -> bool:
    """
    Check if a locator with the given instruction, html, and optional url exists in the cache.
    """
    if SessionLocal is None:
        logger.warning("SessionLocal is None, cannot check existence.")
        return False

    session = SessionLocal()
    try:
        exists = (
            session.query(UILocatorCache.id).filter_by(id=locator_id).first()
            is not None
        )
        logger.debug(f"Locator ID {locator_id} exists: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking existence for locator ID {locator_id}: {e}")
        return False
    finally:
        session.close()


def save_locator(
    instruction: str,
    html: str,
    selector_type: str,
    selector_value: str,
    url: Optional[str] = None,
    project_id=None,
):
    if SessionLocal is None:
        return None

    locator_id = compute_locator_id(instruction, html, url, project_id)
    session = SessionLocal()

    try:
        stmt = (
            insert(UILocatorCache)
            .values(
                id=locator_id,
                url=url,
                user_instruction=instruction,
                html=html,
                selector_type=selector_type,
                selector_value=selector_value,
                project_id=project_id,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "url": url,
                    "user_instruction": instruction,
                    "html": html,
                    "selector_type": selector_type,
                    "selector_value": selector_value,
                    "updated_at": datetime.utcnow(),
                },
            )
        )

        session.execute(stmt)
        session.commit()
        logger.debug(f"Saved or updated locator with ID: {locator_id}")
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Error saving locator: {e}")
        return False
    finally:
        session.close()


def delete_locator(
    instruction: str,
    html: str,
    url: Optional[str] = None,
) -> bool:
    """
    Delete a locator from the cache by its ID.
    Returns True if deleted, False if not found or error occurred.
    """
    if SessionLocal is None:
        logger.warning("SessionLocal is None, skipping deletion.")
        return False

    session = SessionLocal()
    locator_id = compute_locator_id(instruction, html, url)
    try:
        row = session.query(UILocatorCache).filter_by(id=locator_id).first()
        if not row:
            logger.debug(f"No locator found with ID: {locator_id}")
            return False
        session.delete(row)
        session.commit()
        logger.debug(f"Deleted locator with ID: {locator_id}")
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete locator ID {locator_id}: {e}")
        return False
    finally:
        session.close()
