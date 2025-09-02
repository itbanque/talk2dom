from talk2dom.db.models import UILocatorCache, HTML
from talk2dom.db.session import SessionLocal
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

import hashlib
from loguru import logger
from typing import Optional


def compute_locator_id(
    instruction: str,
    html_id: str,
    url: Optional[str] = "",
    project_id: Optional[str] = "",
) -> str:
    if project_id is None:
        project_id = ""
    raw = (instruction.lower().strip() + html_id + project_id.strip()).encode("utf-8")
    uuid = hashlib.sha256(raw).hexdigest()
    logger.debug(
        f"Computing locator ID for instruction: {instruction[:50]}... and html: {html_id}, url: {url}, UUID: {uuid}"
    )
    return uuid


def get_cached_locator(
    instruction: str,
    html: str,
    url: Optional[str] = None,
    project_id: Optional[str] = "",
) -> tuple:
    if SessionLocal is None:
        return None, None, None

    html_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
    locator_id = compute_locator_id(instruction, html_id, url, project_id)
    session = SessionLocal()

    try:
        row = session.query(UILocatorCache).filter_by(id=locator_id).first()
        if row:
            logger.debug(f"Cache hit for locator ID: {locator_id}")
        else:
            logger.debug(f"Cache miss for locator ID: {locator_id}")
        return (
            (row.selector_type, row.selector_value, row.action)
            if row
            else (None, None, None)
        )
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
    html_backbone: str,
    selector_type: str,
    selector_value: str,
    action: Optional[str] = None,
    url: Optional[str] = None,
    project_id=None,
    html=str,
):
    if SessionLocal is None:
        return None

    # html_id = hashlib.sha256(html_backbone.encode("utf-8")).hexdigest()
    html_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
    locator_id = compute_locator_id(instruction, html_id, url, project_id)
    session = SessionLocal()

    try:
        existing_html = session.query(HTML).filter_by(id=html_id).first()
        if not existing_html:
            session.add(
                HTML(id=html_id, row_html=html, backbone=html_backbone, url=url or "")
            )
        stmt = (
            insert(UILocatorCache)
            .values(
                id=locator_id,
                url=url,
                user_instruction=instruction,
                html_id=html_id,
                selector_type=selector_type,
                selector_value=selector_value,
                action=action,
                project_id=project_id,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "url": url,
                    "user_instruction": instruction,
                    "html_id": html_id,
                    "selector_type": selector_type,
                    "selector_value": selector_value,
                    "action": action,
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
