from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import logging
import os
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


@app.middleware("http")
async def add_build_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Readar-Build"] = BUILD_ID
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
# CORS
# ----------------------------
raw = os.getenv("CORS_ORIGINS", "").strip()
cors_origins = [o.strip() for o in raw.split(",") if o.strip()] if raw else []

# Local dev fallback (only if env var missing)
if not cors_origins:
    cors_origins = ["http://localhost:5173"]

# Allow all Vercel preview/prod domains
vercel_origin_regex = r"^https://.*\.vercel\.app$"

logger.info("CORS_ORIGINS(raw)=%s", raw)
logger.info("CORS_ORIGINS(list)=%s", cors_origins)
logger.info("CORS vercel_origin_regex=%s", vercel_origin_regex)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://readar-chi.vercel.app",
        "https://readar.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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
