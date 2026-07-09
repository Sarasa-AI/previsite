import asyncio
import logging
import sys

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.auth.security import get_password_hash
from app.db.database import Base, engine, get_async_session
from app.models.user import User, UserRole
from scripts.seed_drugs import seed_drugs

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 3


async def _wait_for_database() -> None:
    """Wait until the database accepts connections, or exit after retries."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info(
                "Database connection established (attempt %s/%s)",
                attempt,
                MAX_RETRIES,
            )
            return
        except OperationalError as exc:
            last_error = exc
            logger.warning(
                "Database not available (attempt %s/%s): %s",
                attempt,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    logger.critical(
        "Failed to connect to database after %s attempts",
        MAX_RETRIES,
        exc_info=last_error,
    )
    sys.exit(1)


async def _seed_default_doctor() -> None:
    async with get_async_session() as db:
        try:
            result = await db.execute(
                select(User).where(User.email == "bagherzade@doctor.com")
            )
            if result.scalar_one_or_none():
                return
            doctor = User(
                email="bagherzade@doctor.com",
                full_name="bagherzade",
                hashed_password=get_password_hash("0808"),
                role=UserRole.DOCTOR,
                is_active=True,
            )
            db.add(doctor)
            await db.commit()
            logger.info("Default doctor account seeded")
        except Exception:
            await db.rollback()
            logger.exception("Failed to seed default doctor account")


async def init_db() -> None:
    """Create all database tables after the database is reachable."""
    await _wait_for_database()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _seed_default_doctor()
    await seed_drugs(refresh_matcher=False)
    logger.info("Database tables created successfully")
