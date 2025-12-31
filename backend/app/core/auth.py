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
    # Check Supabase configuration before attempting to decode
    try:
        settings.require_supabase()
    except RuntimeError as e:
        logger.error(f"Supabase configuration missing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase environment variables not configured. Authentication is not available.",
        )

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
    email_verified = payload.get("email_verified", False)  # Supabase includes this claim
    
    # Extract endpoint info for logging
    endpoint = f"{request.method} {request.url.path}"

    try:
        user = get_or_create_user_by_auth_id(
            db=db,
            auth_user_id=str(auth_user_id),
            email=str(email),
            endpoint_path=endpoint,
            email_verified=bool(email_verified),
        )
        return user
    except HTTPException as e:
        # Enhanced logging for 409 errors (now only for unsafe conflicts)
        if e.status_code == 409:
            logger.error(
                f"[409_AUTH_CONFLICT] endpoint={endpoint}, "
                f"auth_user_id={auth_user_id}, "
                f"auth_email={email}, "
                f"detail={e.detail}"
            )
        raise
