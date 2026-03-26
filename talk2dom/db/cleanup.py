from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from talk2dom.db.models import APIUsage, User


@dataclass
class CleanupResult:
    matched_rows: int
    deleted_rows: int
    dry_run: bool
    cutoff_time: datetime


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def cleanup_api_usage(
    db: Session,
    older_than_days: int,
    dry_run: bool = True,
    batch_size: int = 1000,
    user_id: Optional[UUID | str] = None,
    user_email: Optional[str] = None,
    project_id: Optional[UUID | str] = None,
) -> CleanupResult:
    if older_than_days < 0:
        raise ValueError("older_than_days must be >= 0")
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    cutoff_time = _utcnow() - timedelta(days=older_than_days)

    if user_id and user_email:
        raise ValueError("Provide either user_id or user_email, not both")

    resolved_user_id = user_id
    if user_email:
        user = db.query(User.id).filter(User.email == user_email).first()
        if user is None:
            return CleanupResult(
                matched_rows=0,
                deleted_rows=0,
                dry_run=dry_run,
                cutoff_time=cutoff_time,
            )
        resolved_user_id = user.id

    query = db.query(APIUsage.id).filter(APIUsage.request_time < cutoff_time)
    if resolved_user_id:
        query = query.filter(APIUsage.user_id == resolved_user_id)
    if project_id:
        query = query.filter(APIUsage.project_id == project_id)

    matched_rows = query.count()
    if dry_run or matched_rows == 0:
        return CleanupResult(
            matched_rows=matched_rows,
            deleted_rows=0,
            dry_run=dry_run,
            cutoff_time=cutoff_time,
        )

    deleted_rows = 0
    while True:
        batch_ids = [
            row_id
            for (row_id,) in query.order_by(APIUsage.request_time)
            .limit(batch_size)
            .all()
        ]
        if not batch_ids:
            break

        deleted = (
            db.query(APIUsage)
            .filter(APIUsage.id.in_(batch_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        deleted_rows += deleted

    return CleanupResult(
        matched_rows=matched_rows,
        deleted_rows=deleted_rows,
        dry_run=False,
        cutoff_time=cutoff_time,
    )
