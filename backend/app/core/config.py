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
    
    # CORS - FRONTEND_ORIGINS takes precedence (comma-separated), falls back to CORS_ORIGINS
    FRONTEND_ORIGINS: Optional[str] = None  # Comma-separated list for production (e.g., "https://app.example.com,https://www.example.com")
    CORS_ORIGINS: str = '["http://localhost:3000", "http://localhost:5173"]'  # Legacy support, can be JSON or comma-separated
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Supabase Auth API (optional - required only for authentication features)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    
    # Supabase JWT verification (local)
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_JWT_AUD: str = "authenticated"
    SUPABASE_JWT_ISS: Optional[str] = None
    
    # Admin access control
    ADMIN_EMAIL_ALLOWLIST: str = ""  # Comma-separated list of admin emails

    # Email configuration (Resend)
    RESEND_API_KEY: Optional[str] = None
    
    model_config = SettingsConfigDict(
        # Load from backend/.env (relative to this file's parent's parent)
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore unknown environment variables (like VITE_*)
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Normalize empty strings: if .env has empty values, fall back to environment variables
        # This prevents empty .env lines (e.g., "DATABASE_URL=") from overriding shell env vars
        import os
        critical_fields = ["DATABASE_URL"]
        for field in critical_fields:
            value = getattr(self, field, None)
            if isinstance(value, str) and value.strip() == "":
                # Empty string in .env - check if environment variable is set
                env_value = os.getenv(field)
                if env_value and env_value.strip():
                    # Use environment variable instead of empty .env value
                    setattr(self, field, env_value)
        
        # Normalize Supabase URL to avoid issuer mismatch like ...co//auth/v1 (if set)
        if self.SUPABASE_URL and isinstance(self.SUPABASE_URL, str):
            self.SUPABASE_URL = self.SUPABASE_URL.rstrip("/")
            # Check for placeholder values (only warn, don't fail)
            if "YOUR_PROJECT_REF" in self.SUPABASE_URL or "YOUR_PROJECT" in self.SUPABASE_URL:
                import warnings
                warnings.warn(
                    "SUPABASE_URL appears to be a placeholder. Set it to your actual Supabase project URL.",
                    UserWarning
                )
        
        # Validate DATABASE_URL is set and not the default placeholder (required)
        default_placeholder = "postgresql://user:password@localhost/readar"
        if not self.DATABASE_URL or self.DATABASE_URL.strip() == "" or self.DATABASE_URL == default_placeholder:
            raise RuntimeError(
                "DATABASE_URL is not set. Create backend/.env with DATABASE_URL=postgresql://postgres:postgres@localhost:5432/readar"
            )
        
        # Set default issuer if SUPABASE_URL is set and JWT_ISS is not explicitly set
        if self.SUPABASE_URL and (not self.SUPABASE_JWT_ISS or (isinstance(self.SUPABASE_JWT_ISS, str) and self.SUPABASE_JWT_ISS.strip() == "")):
            self.SUPABASE_JWT_ISS = f"{self.SUPABASE_URL}/auth/v1"
    
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
        """Parse CORS origins from FRONTEND_ORIGINS (comma-separated) or CORS_ORIGINS (JSON/comma-separated).
        
        Priority:
        1. FRONTEND_ORIGINS (comma-separated) - preferred for production
        2. CORS_ORIGINS (JSON or comma-separated) - legacy support
        3. Default localhost origins for dev
        """
        # Check FRONTEND_ORIGINS first (comma-separated, production-friendly)
        if self.FRONTEND_ORIGINS and self.FRONTEND_ORIGINS.strip():
            origins = [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]
            if origins:
                return origins
        
        # Fall back to CORS_ORIGINS (supports JSON or comma-separated)
        if not self.CORS_ORIGINS:
            return ["http://localhost:5173"]  # Default fallback
        
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
            return origins if origins else ["http://localhost:5173"]
    
    def require_supabase(self) -> None:
        """
        Raise RuntimeError if Supabase environment variables are not configured.
        
        Call this method before using Supabase authentication features.
        This allows the backend to start and run migrations even if Supabase vars are missing.
        """
        missing = []
        
        if not self.SUPABASE_URL or (isinstance(self.SUPABASE_URL, str) and self.SUPABASE_URL.strip() == ""):
            missing.append("SUPABASE_URL")
        elif "YOUR_PROJECT_REF" in self.SUPABASE_URL or "YOUR_PROJECT" in self.SUPABASE_URL:
            missing.append("SUPABASE_URL (appears to be a placeholder)")
        
        if not self.SUPABASE_ANON_KEY or (isinstance(self.SUPABASE_ANON_KEY, str) and self.SUPABASE_ANON_KEY.strip() == ""):
            missing.append("SUPABASE_ANON_KEY")
        elif isinstance(self.SUPABASE_ANON_KEY, str) and ("YOUR_ANON" in self.SUPABASE_ANON_KEY or "YOUR_SUPABASE" in self.SUPABASE_ANON_KEY or len(self.SUPABASE_ANON_KEY) < 20):
            missing.append("SUPABASE_ANON_KEY (appears to be invalid)")
        
        if not self.SUPABASE_JWT_SECRET or (isinstance(self.SUPABASE_JWT_SECRET, str) and self.SUPABASE_JWT_SECRET.strip() == ""):
            missing.append("SUPABASE_JWT_SECRET")
        
        if missing:
            raise RuntimeError(
                f"Supabase environment variables not configured: {', '.join(missing)}. "
                "Set these in your environment to enable authentication features. "
                "Get values from Supabase Project Settings -> API."
            )


settings = Settings()

