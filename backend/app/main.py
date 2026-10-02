from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import (
    admin,
    admin_doctors,
    admin_users,
    chat,
    consent,
    documents,
    files,
    intake,
    medications,
    patients,
    pdf,
    pmh,
    privacy,
    summary,
)
from app.api.routes import auth
from app.auth.dependencies import get_current_active_admin
from app.auth.security import decode_access_token
from app.core.config import is_production_env, settings, validate_startup_config
from app.core.error_handler import register_exception_handlers
from app.core.health_checks import check_database, check_llm_provider, check_migrations
from app.core.inference.infrastructure.composition import (
    close_inference_runtime,
    init_inference_runtime,
)
from app.core.logging_config import setup_logging
from app.core.observability.metrics import metrics_response
from app.core.observability.middleware import CorrelationIdMiddleware
from app.core.sentry import init_sentry
from app.core.startup_health import verify_llm_connection
from app.db.database import get_async_session, get_db
from app.db.init_db import init_db
from app.models.user import User, UserRole
from app.modules.workspace.api import router as workspace_router
from app.services.drug_matcher import drug_matcher

setup_logging()
init_sentry()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize shared resources when the API starts."""
    validate_startup_config()
    await init_db()
    logger.info("Database initialized")
    async with get_async_session() as db:
        await drug_matcher.refresh_cache(db)
    logger.info("Drug matcher cache warmed")
    if settings.SKIP_HEALTH_CHECK:
        logger.warning("Skipping mandatory LLM health check due to configuration.")
    else:
        await verify_llm_connection()

    # Initialize inference runtime (registry + pipeline)
    try:
        registry, pipeline = init_inference_runtime()
        registered = registry.registered_products()
        logger.info("Inference runtime initialized with products: %s", registered)
    except Exception as exc:
        logger.exception("Failed to initialize inference runtime: %s", exc)

    yield

    # Graceful shutdown
    await close_inference_runtime()


# ─────────── ایجاد FastAPI Application ───────────
app = FastAPI(
    title="PreVisit MVP API",
    description="سیستم شرح‌حال پیش از ویزیت با هوش مصنوعی",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─────────── CORS Middleware ───────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID + structured HTTP request logging (outermost after CORS registration → runs first)
app.add_middleware(CorrelationIdMiddleware)

register_exception_handlers(app)

# ─────────── Root Endpoints ───────────
@app.get("/")
def read_root():
    """صفحه اصلی API"""
    return {
        "message": "PreVisit MVP API",
        "status": "running",
        "version": "0.1.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    """بررسی سلامت سرور"""
    return {
        "status": "ok"
    }


def _role_value(user: User) -> str:
    role = user.role
    return role.value if hasattr(role, "value") else str(role)


async def require_metrics_access(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Allow admin JWT or configured METRICS_BEARER_TOKEN; never open anonymously.

    Production without a configured metrics bearer token: unauthenticated
    callers see 404 (endpoint appears disabled). Admin JWT still works.
    """
    configured_token = (settings.metrics_bearer_token or "").strip()
    raw = (authorization or "").strip()
    bearer = ""
    if raw.lower().startswith("bearer "):
        bearer = raw[7:].strip()

    if configured_token and bearer and secrets_compare(bearer, configured_token):
        return

    if bearer:
        payload = decode_access_token(bearer)
        if payload and payload.get("sub"):
            try:
                user_id = int(payload["sub"])
            except (TypeError, ValueError):
                user_id = None
            if user_id is not None:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if (
                    user
                    and user.is_active
                    and _role_value(user) == UserRole.ADMIN.value
                ):
                    return
                if user and user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Metrics access denied",
                    )

    if is_production_env() and not configured_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Metrics authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def secrets_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@app.get("/metrics")
async def prometheus_metrics(_: None = Depends(require_metrics_access)):
    """Prometheus text exposition — admin JWT or METRICS_BEARER_TOKEN only."""
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)


@app.get("/health/detailed")
async def health_detailed(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
):
    """Admin-only dependency status (Database, LLM provider, migrations)."""
    db_status = await check_database(db)
    llm_status = await check_llm_provider()
    migrations_status = await check_migrations(db)
    statuses = [db_status["status"], llm_status["status"]]
    if all(s == "ok" for s in statuses):
        overall = "ok"
    elif any(s == "down" for s in statuses):
        overall = "degraded"
    else:
        overall = "degraded"
    return {
        "status": overall,
        "dependencies": {
            "database": db_status,
            "llm_provider": llm_status,
            "migrations": migrations_status,
        },
    }

# ─────────── Include Routers ───────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin_doctors.router)
app.include_router(admin_users.router)
app.include_router(consent.router)
app.include_router(privacy.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(files.router)
app.include_router(documents.router)
app.include_router(intake.router)
app.include_router(medications.router)
app.include_router(patients.router)
app.include_router(pmh.router)
app.include_router(pdf.router)
app.include_router(workspace_router)
