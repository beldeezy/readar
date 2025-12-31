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
    logger.exception("[UNHANDLED] %s %s", request.method, request.url.path)
    
    # Create response with CORS headers
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
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


@app.on_event("startup")
def on_startup() -> None:
    logger.info("[BOOT] %s", SERVER_BOOT_ID)
    init_db()


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
