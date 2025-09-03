from talk2dom.db.models import UILocatorCache, HTML
from talk2dom.db.session import SessionLocal
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

import hashlib
from loguru import logger
from typing import Optional
import os
import redis  # type: ignore

_redis_client = None


def _redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = (
        os.getenv("T2D_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://localhost:6379/0"
    )
    _redis_client = redis.from_url(url, decode_responses=True, socket_timeout=0.5)
    return _redis_client


# Redis cache settings
_TTL_SECONDS = int(os.getenv("T2D_REDIS_TTL", "86400"))  # default 1 day
_NS = os.getenv("T2D_REDIS_NS", "t2d:v1")


def _locator_key(locator_id: str) -> str:
    return f"{_NS}:loc:{locator_id}"


def _redis_set_locator(
    locator_id: str,
    selector_type: Optional[str],
    selector_value: Optional[str],
    action: Optional[str],
) -> None:
    r = _redis()
    logger.debug(f"Redis set locator {locator_id}")
    # Use a compact hash to avoid JSON overhead
    mapping = {
        "t": selector_type or "",
        "v": selector_value or "",
        "a": action or "",
    }
    r.hset(_locator_key(locator_id), mapping=mapping)
    if _TTL_SECONDS > 0:
        r.expire(_locator_key(locator_id), _TTL_SECONDS)


def _redis_get_locator(locator_id: str) -> tuple:
    r = _redis()
    data = r.hgetall(_locator_key(locator_id))
    logger.debug(f"Redis get locator {locator_id}")
    if not data:
        return None, None, None
    t = data.get("t") or None
    v = data.get("v") or None
    a = data.get("a") or None
    if not (t or v or a):
        return None, None, None
    return t, v, a


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

    src = (url or "").strip() or (html or "")
    html_id = hashlib.sha256(src.encode("utf-8")).hexdigest()
    locator_id = compute_locator_id(instruction, html_id, url, project_id)

    # Try Redis first
    t, v, a = _redis_get_locator(locator_id)
    if t or v or a:
        logger.debug(f"Redis hit for locator ID: {locator_id}")
        return t, v, a

    session = SessionLocal()
    try:
        row = session.query(UILocatorCache).filter_by(id=locator_id).first()
        if not row:
            logger.debug(f"DB miss for locator ID: {locator_id}")
            return None, None, None
        logger.debug(f"DB hit for locator ID: {locator_id}")
        # Backfill Redis for subsequent lookups
        _redis_set_locator(
            locator_id, row.selector_type, row.selector_value, row.action
        )
        return row.selector_type, row.selector_value, row.action
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

    src = (url or "").strip() or (html_backbone or "").strip() or (html or "")
    html_id = hashlib.sha256(src.encode("utf-8")).hexdigest()
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
        # Write-through cache so reads don't have to hit DB
        _redis_set_locator(locator_id, selector_type, selector_value, action)
        session.close()
