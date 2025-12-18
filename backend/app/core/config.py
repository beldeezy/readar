from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import json
import os
from pathlib import Path


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/readar"
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_ID: Optional[str] = None
    
    # CORS - can be JSON string or comma-separated string
    CORS_ORIGINS: str = '["http://localhost:3000", "http://localhost:5173"]'
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Supabase Auth API
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    
    # Supabase JWT verification (local)
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_AUD: str = "authenticated"
    SUPABASE_JWT_ISS: str = ""
    
    # Admin access control
    ADMIN_EMAIL_ALLOWLIST: str = ""  # Comma-separated list of admin emails
    
    model_config = SettingsConfigDict(
        # Load from backend/.env (relative to this file's parent's parent)
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore unknown environment variables (like VITE_*)
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validate DATABASE_URL is set and not the default placeholder
        default_placeholder = "postgresql://user:password@localhost/readar"
        if not self.DATABASE_URL or self.DATABASE_URL.strip() == "" or self.DATABASE_URL == default_placeholder:
            raise RuntimeError(
                "DATABASE_URL is not set. Create backend/.env with DATABASE_URL=postgresql://postgres:postgres@localhost:5432/readar"
            )
        
        # Validate Supabase configuration (required for authentication)
        if not self.SUPABASE_URL or self.SUPABASE_URL.strip() == "":
            raise RuntimeError(
                "SUPABASE_URL is not set. Create backend/.env with SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co"
            )
        
        # Check for placeholder values
        if "YOUR_PROJECT_REF" in self.SUPABASE_URL or "YOUR_PROJECT" in self.SUPABASE_URL:
            raise RuntimeError(
                "SUPABASE_URL appears to be a placeholder. Set it to your actual Supabase project URL in backend/.env"
            )
        
        if not self.SUPABASE_ANON_KEY or self.SUPABASE_ANON_KEY.strip() == "":
            raise RuntimeError(
                "SUPABASE_ANON_KEY is not set. Create backend/.env with SUPABASE_ANON_KEY=YOUR_ANON_PUBLIC_KEY"
            )
        
        # Check for placeholder values
        if "YOUR_ANON" in self.SUPABASE_ANON_KEY or "YOUR_SUPABASE" in self.SUPABASE_ANON_KEY or len(self.SUPABASE_ANON_KEY) < 20:
            raise RuntimeError(
                "SUPABASE_ANON_KEY appears to be a placeholder or invalid. Set it to your actual Supabase anon key in backend/.env"
            )
        
        # Default issuer if not explicitly set
        if not self.SUPABASE_JWT_ISS or self.SUPABASE_JWT_ISS.strip() == "":
            self.SUPABASE_JWT_ISS = f"{self.SUPABASE_URL}/auth/v1"
        
        # Validate JWT secret (required for local token verification)
        if not self.SUPABASE_JWT_SECRET or self.SUPABASE_JWT_SECRET.strip() == "":
            raise RuntimeError(
                "SUPABASE_JWT_SECRET is not set. Add SUPABASE_JWT_SECRET from your Supabase Project Settings -> API -> JWT Secret."
            )
    
    def get_masked_database_url(self) -> str:
        """Return DATABASE_URL with password masked for logging."""
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(self.DATABASE_URL)
            # Mask password
            masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                masked_netloc += f":{parsed.port}"
            masked = urlunparse((
                parsed.scheme,
                masked_netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return masked
        except Exception:
            # Fallback: just show scheme and host
            return f"{self.DATABASE_URL.split('@')[0].split('://')[0]}://<user>:***@{self.DATABASE_URL.split('@')[-1] if '@' in self.DATABASE_URL else 'localhost'}"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS from JSON string or comma-separated string."""
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000", "http://localhost:5173"]
        
        try:
            # Try parsing as JSON first
            parsed = json.loads(self.CORS_ORIGINS)
            if isinstance(parsed, list):
                return parsed
            # If it's a string, treat as single origin
            return [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            # Fall back to comma-separated string
            origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
            return origins if origins else ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()

