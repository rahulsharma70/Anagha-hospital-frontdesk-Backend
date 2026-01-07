"""
Configuration file for server settings
Can be overridden by environment variables
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from current directory or parent directory
env_path = Path(__file__).parent / ".env"
parent_env_path = Path(__file__).parent.parent / ".env"

# Try to load from parent first (since that's where the user placed it)
if parent_env_path.exists():
    load_dotenv(parent_env_path, override=True)
elif env_path.exists():
    load_dotenv(env_path, override=True)
else:
    # Try default locations (current working directory)
    load_dotenv(override=True)

# Server Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))

# API Configuration (for Flutter app)
API_BASE_URL = os.getenv("API_BASE_URL", f"http://{SERVER_HOST}:{SERVER_PORT}")

# Admin Panel Configuration
ADMIN_PANEL_PORT = int(os.getenv("ADMIN_PANEL_PORT", SERVER_PORT))
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", f"http://{SERVER_HOST}:{ADMIN_PANEL_PORT}/admin_panel.html")

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Email Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "mail.anaghasafar.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "info@anaghasafar.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "Uabiotech*2309")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "info@anaghasafar.com")

# Admin Configuration
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "info@uabiotech.in")
ADMIN_WHATSAPP = os.getenv("ADMIN_WHATSAPP", "+919039939555")

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "anagha-hospital-solutions-secret-key-2024")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Supabase client (for package_service)
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize Supabase in config: {e}")
        supabase = None

