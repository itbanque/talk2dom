from __future__ import annotations

import argparse
from uuid import UUID

from dotenv import load_dotenv

from talk2dom.db.cleanup import cleanup_api_usage
from talk2dom.db.session import SessionLocal


def _parse_uuid(value: str) -> UUID:
    return UUID(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean old rows from the api_usage table."
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        required=True,
        help="Delete rows with request_time older than this many days.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Delete rows in batches of this size.",
    )
    parser.add_argument(
        "--user-id",
        type=_parse_uuid,
        help="Only clean rows for this user ID.",
    )
    parser.add_argument(
        "--user-email",
        help="Only clean rows for this user email.",
    )
    parser.add_argument(
        "--project-id",
        type=_parse_uuid,
        help="Only clean rows for this project ID.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete rows. Without this flag, the script runs in dry-run mode.",
    )
    return parser


def main() -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    if SessionLocal is None:
        parser.error("TALK2DOM_DB_URI is not configured.")
    if args.user_id and args.user_email:
        parser.error("Use either --user-id or --user-email, not both.")

    session = SessionLocal()
    try:
        result = cleanup_api_usage(
            db=session,
            older_than_days=args.older_than_days,
            dry_run=not args.confirm,
            batch_size=args.batch_size,
            user_id=args.user_id,
            user_email=args.user_email,
            project_id=args.project_id,
        )
    finally:
        session.close()

    mode = "DRY RUN" if result.dry_run else "DELETE"
    print(
        f"[{mode}] cutoff={result.cutoff_time.isoformat()} "
        f"matched_rows={result.matched_rows} deleted_rows={result.deleted_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
