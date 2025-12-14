from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
)
from app.database import init_db

app = FastAPI(debug=True)

# DEV-ONLY CORS: wide open for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(books.router)
app.include_router(recommendations.router)
app.include_router(user_books.router)
app.include_router(billing.router)
app.include_router(reading_history.router)
app.include_router(debug.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health_check():
    return {"status": "ok"}
