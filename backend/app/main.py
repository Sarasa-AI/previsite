from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import admin, chat, documents, files, intake, patients, pdf, pmh, summary
from app.api.routes import auth
from app.auth.dependencies import get_current_active_admin
from app.core.config import settings, validate_startup_config
from app.core.error_handler import register_exception_handlers
from app.core.health_checks import check_database, check_llm_provider, check_ollama
from app.core.logging_config import setup_logging
from app.core.observability.metrics import metrics_response
from app.core.observability.middleware import CorrelationIdMiddleware
from app.core.sentry import init_sentry
from app.core.startup_health import verify_llm_connection
from app.db.database import get_async_session, get_db
from app.db.init_db import init_db
from app.models.user import User
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
    yield

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


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus text exposition of Clinical AI pipeline metrics."""
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)


@app.get("/health/detailed")
async def health_detailed(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
):
    """Admin-only dependency status (DB, Ollama, LLM provider)."""
    db_status = await check_database(db)
    ollama_status = await check_ollama()
    llm_status = await check_llm_provider()
    statuses = [db_status["status"], ollama_status["status"], llm_status["status"]]
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
            "ollama": ollama_status,
            "llm_provider": llm_status,
        },
    }

# ─────────── Include Routers ───────────
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(files.router)
app.include_router(documents.router)
app.include_router(intake.router)
app.include_router(patients.router)
app.include_router(pmh.router)
app.include_router(pdf.router)
