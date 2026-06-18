import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.api import chat, summary, files, intake
from app.core.config import settings, validate_startup_config
from app.core.error_handler import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.startup_health import verify_llm_connection
from app.db.init_db import init_db

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize shared resources when the API starts."""
    validate_startup_config()
    init_db()
    logger.info("Database initialized")
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
async def request_logging_middleware(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Request failed method=%s path=%s", request.method, request.url.path)
        raise
    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "HTTP %s %s status=%s duration_ms=%s",
        request.method,
        request.url.path,
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
        "status": "healthy",
        "service": "PreVisit MVP"
    }

# ─────────── Include Routers ───────────
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(summary.router)
app.include_router(files.router)
app.include_router(intake.router)
