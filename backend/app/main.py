from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response, JSONResponse
import logging
import os
import re
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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
    }


# CORS configuration - robust parsing of CORS_ORIGINS env var
# Read CORS_ORIGINS from environment (string of comma-separated origins)
raw = os.getenv("CORS_ORIGINS", "").strip()

# Split by commas, strip whitespace, discard empties
cors_origins = []
if raw:
    cors_origins = [o.strip() for o in raw.split(",") if o.strip()]

# Temporary startup log to verify what Render is reading
print("CORS_ORIGINS(raw) =", raw)
print("CORS_ORIGINS(list) =", cors_origins)

# Vercel regex pattern for origin matching
vercel_re = re.compile(r"^https://.*\.vercel\.app$")


def is_allowed_origin(origin: str) -> bool:
    """Check if an origin is allowed based on cors_origins list or Vercel regex."""
    if not origin:
        return False
    if origin in cors_origins:
        return True
    if vercel_re.match(origin):
        return True
    return False


# CORSMiddleware (belt + suspenders approach)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https://.*\.vercel\.app$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORS safety-net middleware (runs AFTER CORSMiddleware to patch missing headers)
@app.middleware("http")
async def cors_safety_net(request: Request, call_next):
    """Safety-net middleware to ensure CORS headers are always set correctly."""
    origin = request.headers.get("origin")
    
    if request.method == "OPTIONS":
        # Preflight request - return 204 quickly with headers
        resp = Response(status_code=204)
    else:
        resp = await call_next(request)
    
    # Only set CORS headers if origin is allowed
    if is_allowed_origin(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "access-control-request-headers", "*"
        )
        resp.headers["Vary"] = "Origin"
    
    return resp


# Routers
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
    print(f"[BOOT] {SERVER_BOOT_ID}")
    init_db()
    
    # Dev-only: Print registered routes for debugging
    if settings.DEBUG:
        from fastapi.routing import APIRoute
        print("\n" + "="*60)
        print("Registered API Routes:")
        print("="*60)
        for route in app.routes:
            if isinstance(route, APIRoute):
                methods = ', '.join(sorted(route.methods)) if route.methods else 'N/A'
                print(f"  {methods:20} {route.path}")
        print("="*60 + "\n")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/cors-test")
def cors_test():
    """Simple CORS test endpoint to verify CORS headers are working."""
    return {"ok": True}


@app.get("/api/health")
def api_health_check():
    """Health check endpoint under /api for frontend consistency."""
    return {"status": "ok"}


@app.get("/api/_debug/cors")
def cors_debug():
    """Debug endpoint to verify CORS headers are working."""
    return {"ok": True}


@app.get("/api/_debug/echo-origin")
def echo_origin(req: Request):
    """Debug endpoint to see request origin and CORS headers."""
    return {
        "origin": req.headers.get("origin"),
        "host": req.headers.get("host"),
        "path": str(req.url.path),
    }


@app.get("/api/_debug/server-id")
def server_id():
    """Server fingerprint endpoint to verify which backend instance is responding."""
    return {"server_id": SERVER_BOOT_ID}


# Backwards-compatible redirect for /books -> /api/books
@app.get("/books")
def books_compat_redirect():
    return RedirectResponse(url="/api/books")
