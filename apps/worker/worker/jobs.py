"""Scheduled jobs. Run with: python -m worker.jobs <job-name>

Intended to be triggered by Railway cron (see docs/DEPLOYMENT.md).
"""

import asyncio
import logging
import sys
from datetime import timedelta

from sqlalchemy import func, select

from app.core.logging import configure_logging
from app.core.security import utcnow
from app.db.session import get_sessionmaker
from app.models import Listing
from app.models.enums import ListingStatus

log = logging.getLogger("ajar.worker")


async def freshness_report() -> dict[str, int]:
    """Count expired and soon-to-expire published listings.

    Expired listings are already hidden from public queries (status stays `published` so the publisher can
    re-confirm with one click). M4 extends this job to send reminders to publishers.
    """
    now = utcnow()
    async with get_sessionmaker()() as session:
        base = select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.published)
        expired = await session.scalar(base.where(Listing.expires_at <= now)) or 0
        soon = (
            await session.scalar(
                base.where(Listing.expires_at > now, Listing.expires_at <= now + timedelta(days=3))
            )
            or 0
        )
    result = {"expired": expired, "expiring_within_3_days": soon}
    log.info("freshness report", extra={"extra_fields": result})
    return result


JOBS = {"freshness_report": freshness_report}


def main() -> None:
    configure_logging()
    if len(sys.argv) != 2 or sys.argv[1] not in JOBS:
        print(f"usage: python -m worker.jobs [{'|'.join(JOBS)}]", file=sys.stderr)
        sys.exit(2)
    asyncio.run(JOBS[sys.argv[1]]())


if __name__ == "__main__":
    main()
