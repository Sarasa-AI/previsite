import asyncio
import logging
import secrets
import sys

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.auth.security import get_password_hash
from app.core.config import settings
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


def _resolve_seed_doctor_password() -> str:
    """Return seed password from env, or generate one for non-production."""
    configured = (settings.seed_doctor_password or "").strip()
    if configured:
        return configured

    env = (settings.app_env or "").strip().lower()
    if env == "production":
        raise SystemExit(
            "FATAL: SEED_DOCTOR_PASSWORD must be set when APP_ENV/ENVIRONMENT=production."
        )

    generated = secrets.token_urlsafe(18)
    if env in {"development", "staging", "test", ""}:
        logger.warning(
            "SEED_DOCTOR_PASSWORD was not set; generated a temporary password for "
            "the default doctor account (%s). "
            "Copy it now — it will not be shown again: %s",
            settings.seed_doctor_username,
            generated,
        )
    else:
        logger.warning(
            "SEED_DOCTOR_PASSWORD was not set; generated a temporary password "
            "(not printed because APP_ENV=%s).",
            settings.app_env,
        )
    return generated


async def _seed_default_doctor() -> None:
    username = (settings.seed_doctor_username or "bagherzade").strip() or "bagherzade"
    email = f"{username}@doctor.com"
    password = _resolve_seed_doctor_password()

    async with get_async_session() as db:
        try:
            result = await db.execute(select(User).where(User.email == email))
            if result.scalar_one_or_none():
                return
            doctor = User(
                email=email,
                full_name=username,
                hashed_password=get_password_hash(password),
                role=UserRole.DOCTOR,
                is_active=True,
            )
            db.add(doctor)
            await db.commit()
            logger.info("Default doctor account seeded email=%s", email)
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
