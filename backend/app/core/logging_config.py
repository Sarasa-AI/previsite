import logging
import sys

from loguru import logger

from app.core.config import settings
from app.core.observability.context import get_context

LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
LOG_FILE_PATH = "/tmp/previsit-backend.log"
JSON_LOG_FILE_PATH = "/tmp/previsit-backend.json.log"


def _enrich_record(record: dict) -> bool:
    """Inject correlation context into every Loguru record (PHI-safe fields only)."""
    ctx = get_context()
    extra = record["extra"]
    for key, value in ctx.as_log_extra().items():
        extra.setdefault(key, value)
    return True


class InterceptHandler(logging.Handler):
    """Bridge stdlib logging records into Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    normalized_level = settings.log_level.upper()

    logger.remove()

    logger.add(
        sys.stderr,
        level=normalized_level,
        format=LOG_FORMAT,
        colorize=True,
        backtrace=True,
        diagnose=False,
        filter=_enrich_record,
    )

    logger.add(
        LOG_FILE_PATH,
        level=normalized_level,
        format=LOG_FORMAT,
        colorize=False,
        rotation="10 MB",
        retention="7 days",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        filter=_enrich_record,
    )

    logger.add(
        JSON_LOG_FILE_PATH,
        level=normalized_level,
        serialize=True,
        colorize=False,
        rotation="10 MB",
        retention="7 days",
        backtrace=True,
        diagnose=False,
        enqueue=True,
        filter=_enrich_record,
    )

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(normalized_level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy"):
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers = [InterceptHandler()]
        stdlib_logger.propagate = False
        stdlib_logger.setLevel(normalized_level)
