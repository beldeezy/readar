from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.routers import (
    auth,
    onboarding,
    books,
    recommendations,
    user_books,
    billing,
    reading_history,
    debug,
    admin_debug,
    me,
    events,
    book_status,
    feedback,
)
from app.database import init_db

# ----------------------------
# Logging
# ----------------------------
logger = logging.getLogger("readar")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Server fingerprint for debugging
SERVER_BOOT_ID = f"readar-backend::{os.getpid()}::{datetime.utcnow().isoformat()}"

app = FastAPI(debug=settings.DEBUG)

BUILD_ID = os.getenv("BUILD_ID", "missing")


# ----------------------------
# CORS - Render + Vercel production origins
# ----------------------------
def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [o.strip() for o in raw.split(",") if o.strip()]


default_origins = [
    "https://readar.ai",
    "https://www.readar.ai",
    "https://readar-chi.vercel.app",
    "http://localhost:5173",
]

raw = os.getenv("CORS_ORIGINS")
cors_origins = _parse_cors_origins(raw) or default_origins
logger.info("[CORS] allow_origins=%s (raw=%s)", cors_origins, raw)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_build_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Readar-Build"] = BUILD_ID
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Always log full exception with stacktrace
    error_type = type(exc).__name__
    error_message = str(exc) if str(exc) else "An unexpected error occurred"
    logger.exception(
        "[UNHANDLED EXCEPTION] %s %s - %s: %s",
        request.method,
        request.url.path,
        error_type,
        error_message
    )
    
    # Create response with detailed error info (safe, no secrets)
    response = JSONResponse(
        status_code=500,
        content={
            "detail": "internal_error",
            "error_type": error_type,
            "error": error_message,
        }
    )
    
    # Ensure CORS headers are present in error responses
    origin = request.headers.get("origin")
    if origin and origin in cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response


@app.get("/__debug")
def __debug():
    return {
        "build_id": BUILD_ID,
        "cors_origins_raw": os.getenv("CORS_ORIGINS", "missing"),
        "file": str(Path(__file__).resolve()),
        "server_boot_id": SERVER_BOOT_ID,
    }


# ----------------------------
# Routers
# ----------------------------
app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(books.router, prefix="/api")
app.include_router(recommendations.router, prefix="/api")
app.include_router(user_books.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(reading_history.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(book_status.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(debug.router, prefix="/api")
app.include_router(admin_debug.router, prefix="/admin")

# Debug: Print registered routes containing "onboarding" (only when DEBUG=true)
# Note: This runs at module import time, so routes are registered
DEBUG_ROUTES = os.getenv("DEBUG", "false").lower() == "true"
if DEBUG_ROUTES:
    logger.info("[DEBUG] Registered routes containing 'onboarding':")
    for route in app.routes:
        if hasattr(route, "path") and "onboarding" in route.path.lower():
            methods = getattr(route, "methods", set())
            logger.info(f"  {', '.join(methods)} {route.path}")


@app.on_event("startup")
def on_startup() -> None:
    logger.info("[BOOT] %s", SERVER_BOOT_ID)

    # Log Supabase and database configuration (safe, no secrets)
    from app.core.config import settings
    from urllib.parse import urlparse

    # Log Supabase URL (safe - just hostname/project ref)
    if settings.SUPABASE_URL:
        try:
            supabase_parsed = urlparse(settings.SUPABASE_URL)
            supabase_host = supabase_parsed.netloc or supabase_parsed.path
            # Extract project ref if it's a supabase.co URL
            if '.supabase.co' in supabase_host:
                project_ref = supabase_host.split('.supabase.co')[0]
                logger.info(f"[CONFIG] SUPABASE_URL hostname={supabase_host}, project_ref={project_ref}")
            else:
                logger.info(f"[CONFIG] SUPABASE_URL hostname={supabase_host}")
        except Exception as e:
            logger.warning(f"[CONFIG] Could not parse SUPABASE_URL: {e}")
    else:
        logger.warning("[CONFIG] SUPABASE_URL not set")

    # Log database host (safe - no password)
    try:
        db_parsed = urlparse(settings.DATABASE_URL)
        db_host = db_parsed.hostname or "unknown"
        db_port = db_parsed.port or 5432
        db_name = db_parsed.path.lstrip('/') if db_parsed.path else "unknown"
        logger.info(f"[CONFIG] DATABASE_URL host={db_host}, port={db_port}, database={db_name}")
    except Exception as e:
        logger.warning(f"[CONFIG] Could not parse DATABASE_URL: {e}")

    init_db()

    # Start background scheduler for weekly email reports
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("[SCHEDULER] Background scheduler started successfully")
    except Exception as e:
        logger.exception(f"[SCHEDULER] Failed to start background scheduler: {e}")
        logger.warning("[SCHEDULER] Weekly email reports will not be sent automatically")
    
    # Debug: Print enum values for onboarding-related enums (only when DEBUG=true)
    DEBUG_ENUMS = os.getenv("DEBUG", "false").lower() == "true"
    if DEBUG_ENUMS:
        from app.models import BusinessStage, SubscriptionStatus, User, OnboardingProfile
        import sqlalchemy as sa
        
        logger.info("[DEBUG] Enum values for onboarding-related types:")
        
        # BusinessStage enum
        logger.info("BusinessStage enum values:")
        for stage in BusinessStage:
            logger.info(f"  {stage.name} = {stage.value!r}")
        
        # SubscriptionStatus enum
        logger.info("SubscriptionStatus enum values:")
        for status in SubscriptionStatus:
            logger.info(f"  {status.name} = {status.value!r}")
        
        # SQLAlchemy column types
        logger.info("[DEBUG] SQLAlchemy column types:")
        logger.info(f"  User.subscription_status type: {User.subscription_status.type}")
        logger.info(f"  OnboardingProfile.business_stage type: {OnboardingProfile.business_stage.type}")
        
        # Check if using PostgresEnum or SQLEnum
        if hasattr(User.subscription_status.type, 'enums'):
            logger.info(f"  User.subscription_status.enums: {User.subscription_status.type.enums}")
        if hasattr(OnboardingProfile.business_stage.type, 'enums'):
            logger.info(f"  OnboardingProfile.business_stage.enums: {OnboardingProfile.business_stage.type.enums}")


@app.on_event("shutdown")
def on_shutdown() -> None:
    """Clean shutdown of background tasks."""
    logger.info("[SHUTDOWN] Stopping background scheduler")
    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("[SHUTDOWN] Background scheduler stopped")
    except Exception as e:
        logger.exception(f"[SHUTDOWN] Error stopping scheduler: {e}")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/health")
def api_health_check():
    return {"status": "ok"}


@app.get("/api/_debug/echo-origin")
def echo_origin(req: Request):
    return {
        "origin": req.headers.get("origin"),
        "host": req.headers.get("host"),
        "path": str(req.url.path),
    }


@app.get("/api/_debug/server-id")
def server_id():
    return {"server_id": SERVER_BOOT_ID}


# Backwards-compatible redirect for /books -> /api/books
@app.get("/books")
def books_compat_redirect():
    return RedirectResponse(url="/api/books")
