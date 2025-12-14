from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import json


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
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore unknown environment variables (like VITE_*)
    )
    
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

