"""
Backward-compatible auth module that delegates to Supabase Auth API.
"""
from fastapi import Depends
from typing import Dict, Any
from app.core.supabase_auth import get_supabase_user


# Backward-compatible alias: existing routers import get_current_user from here
async def get_current_user(
    user: Dict[str, Any] = Depends(get_supabase_user)
) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user.
    
    Delegates to get_supabase_user which validates tokens via Supabase Auth API.
    
    Returns a dict with:
    - id: The Supabase user UUID
    - auth_user_id: Same as id (for backward compatibility)
    - user_id: Same as id (for backward compatibility)
    - email: User email
    """
    # Ensure backward compatibility: add user_id alias if not present
    if "user_id" not in user:
        user["user_id"] = user.get("id") or user.get("auth_user_id")
    return user

