import logging
from logging.config import dictConfig

from app.core.config import settings


def setup_logging() -> None:
    normalized_level = settings.log_level.upper()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "level": normalized_level,
                "handlers": ["console"],
            },
            "loggers": {
                "uvicorn.error": {"level": normalized_level},
                "uvicorn.access": {"level": normalized_level},
            },
        }
    )


logger = logging.getLogger("previsit")
