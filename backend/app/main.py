from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import logging
import os
from datetime import datetime
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

# CORS configuration - reads from FRONTEND_ORIGINS or CORS_ORIGINS env vars
# Note: allow_headers=["*"] includes Authorization header needed for Bearer tokens
ALLOWED_ORIGINS = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # must include Authorization
)

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
app.include_router(debug.router, prefix="/api")
app.include_router(admin_debug.router, prefix="/admin")


@app.on_event("startup")
def on_startup() -> None:
    print(f"[BOOT] {SERVER_BOOT_ID}")
    init_db()
    
    # Log CORS allowed origins when DEBUG is enabled
    if settings.DEBUG:
        print(f"[CORS] Allowed origins: {ALLOWED_ORIGINS}")
    
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
