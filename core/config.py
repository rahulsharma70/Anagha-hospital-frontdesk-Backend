from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Resolve the project root .env file (backend/../.env)
_THIS_DIR = Path(__file__).resolve().parent          # backend/core/
_BACKEND_DIR = _THIS_DIR.parent                      # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent                  # Hospital/
_ENV_FILE = _PROJECT_ROOT / ".env"

class Settings(BaseSettings):
    # Server config
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    ENVIRONMENT: str = "development"

    # API config
    API_BASE_URL: str = "http://localhost:8000"
    
    # Frontend config
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # JWT Auth
    JWT_SECRET: str = "anagha-hospital-solutions-secret-key-2024"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # SMTP
    SMTP_HOST: str = "mail.anaghasafar.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "info@anaghasafar.com"
    SMTP_PASSWORD: str = "Uabiotech*2309"
    SMTP_FROM_EMAIL: str = "info@anaghasafar.com"
    
    # Admin details
    ADMIN_EMAIL: str = "info@uabiotech.in"
    ADMIN_WHATSAPP: str = "+919039939555"

    # Redis config (for rate limiting, etc.)
    REDIS_URL: str = "redis://localhost:6379"
    
    # Payment gateway selector: "razorpay" or "cashfree"
    PAYMENT_GATEWAY: str = "razorpay"
    
    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    
    # Cashfree
    CASHFREE_CLIENT_ID: str = ""
    CASHFREE_CLIENT_SECRET: str = ""
    CASHFREE_ENVIRONMENT: str = "sandbox"  # "sandbox" or "production"
    
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
