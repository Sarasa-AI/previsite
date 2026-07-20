import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import auth
from app.api import admin, chat, documents, summary, files, intake, patients, pmh, pdf
from app.core.config import settings, validate_startup_config
from app.core.error_handler import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.startup_health import verify_llm_connection
from app.db.database import get_async_session
from app.db.init_db import init_db
from app.services.drug_matcher import drug_matcher

setup_logging()


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


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start = time.time()
    client_ip = request.client.host if request.client else "unknown"
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Request failed method={} path={} client_ip={}",
            request.method,
            request.url.path,
            client_ip,
        )
        raise
    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "HTTP {} {} client_ip={} status={} duration_ms={}",
        request.method,
        request.url.path,
        client_ip,
        response.status_code,
        duration_ms,
    )
    return response

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
