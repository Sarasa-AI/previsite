import logging
import sys
import time

from sqlalchemy.exc import OperationalError

from app.db.database import Base, engine, SessionLocal
from app.models import User, Session, Message, File, Summary, Intake
from app.models.user import UserRole
from app.auth.security import get_password_hash

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 3


def _wait_for_database() -> None:
    """Wait until the database accepts connections, or exit after retries."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with engine.connect():
                pass
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
                time.sleep(RETRY_DELAY_SECONDS)

    logger.critical(
        "Failed to connect to database after %s attempts",
        MAX_RETRIES,
        exc_info=last_error,
    )
    sys.exit(1)


def _seed_default_doctor() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "bagherzade@doctor.com").first()
        if existing:
            return
        doctor = User(
            email="bagherzade@doctor.com",
            full_name="bagherzade",
            hashed_password=get_password_hash("0808"),
            role=UserRole.DOCTOR,
            is_active=True,
        )
        db.add(doctor)
        db.commit()
        logger.info("Default doctor account seeded")
    except Exception:
        db.rollback()
        logger.exception("Failed to seed default doctor account")
    finally:
        db.close()


def init_db():
    """Create all database tables after the database is reachable."""
    _wait_for_database()
    Base.metadata.create_all(bind=engine)
    _seed_default_doctor()
    logger.info("Database tables created successfully")
