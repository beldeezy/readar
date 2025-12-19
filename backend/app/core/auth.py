"""
Authentication helpers for verifying Supabase JWTs and resolving the current app User.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import User
from app.core.user_helpers import get_or_create_user_by_auth_id

logger = logging.getLogger(__name__)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_bearer_token(request: Request) -> str:
    """
    Extract 'Bearer <token>' from Authorization header.
    """
    auth = request.headers.get("Authorization")
    if not auth:
        raise _unauthorized("Missing Authorization header")

    parts = auth.split()
    if len(parts) != 2:
        raise _unauthorized("Invalid Authorization header format. Expected 'Bearer <token>'")

    scheme, token = parts
    if scheme.lower() != "bearer":
        raise _unauthorized("Invalid auth scheme. Expected 'Bearer'")

    if not token.strip():
        raise _unauthorized("Empty bearer token")

    return token


def _decode_supabase_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate Supabase access token.

    Assumes HS256 using SUPABASE_JWT_SECRET (common for Supabase projects).
    Validates issuer and audience.
    """
    if not settings.SUPABASE_JWT_SECRET:
        # Fail loudly if config is missing
        logger.error("SUPABASE_JWT_SECRET is not set")
        raise _unauthorized("Server auth configuration missing")

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=settings.SUPABASE_JWT_AUD,
            issuer=settings.SUPABASE_JWT_ISS,
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise _unauthorized("Token validation failed")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: returns the current authenticated User (SQLAlchemy object).

    - Reads Authorization: Bearer <token>
    - Verifies JWT
    - Extracts sub (Supabase user id) and email
    - Upserts into local users table via get_or_create_user_by_auth_id()
    """
    token = _extract_bearer_token(request)
    payload = _decode_supabase_jwt(token)

    auth_user_id = payload.get("sub")
    if not auth_user_id:
        raise _unauthorized("Token missing subject (sub)")

    email = payload.get("email") or ""

    user = get_or_create_user_by_auth_id(
        db=db,
        auth_user_id=str(auth_user_id),
        email=str(email),
    )
    return user
