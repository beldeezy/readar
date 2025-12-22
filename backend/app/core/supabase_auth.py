"""
Supabase authentication utilities using local JWT verification.
"""
from typing import Dict, Any

from fastapi import HTTPException, status, Request

from jose import jwt, JWTError

from app.core.config import settings

import logging


logger = logging.getLogger(__name__)


def _extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        scheme, token = authorization.split(maxsplit=1)
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Expected 'Bearer'",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_supabase_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user from a Supabase access token.

    Validates JWT locally using SUPABASE_JWT_SECRET, expected issuer and audience.
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
    
    token = _extract_bearer_token(request)

    try:
        # Validate token locally
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=settings.SUPABASE_JWT_AUD,
            issuer=settings.SUPABASE_JWT_ISS,
        )

        user_id = payload.get("sub")
        email = payload.get("email", "") or ""

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing subject (sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "id": user_id,
            "email": email,
            "auth_user_id": user_id,
            "claims": payload,
        }

    except HTTPException:
        raise
    except JWTError as e:
        logger.warning(f"Supabase token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error validating token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if user email is in admin allowlist.
    """
    email = user.get("email", "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User email not available",
        )

    allowlist_str = getattr(settings, "ADMIN_EMAIL_ALLOWLIST", "")
    if not allowlist_str:
        logger.warning("ADMIN_EMAIL_ALLOWLIST not configured - denying all admin access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access not configured",
        )

    allowlist = [e.strip().lower() for e in allowlist_str.split(",") if e.strip()]

    if email not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user


async def get_admin_user(request: Request) -> Dict[str, Any]:
    user = await get_supabase_user(request)
    return require_admin(user)
