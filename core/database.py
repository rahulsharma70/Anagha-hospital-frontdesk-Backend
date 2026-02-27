from supabase import create_client, Client
from typing import Optional
from core.config import settings
import logging

logger = logging.getLogger(__name__)

supabase: Optional[Client] = None

def init_db():
    global supabase
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        logger.error(
            "❌ SUPABASE_URL or SUPABASE_KEY is empty! "
            f"Check that your .env file exists and is readable. "
            f"Expected .env path: {settings.model_config.get('env_file', 'unknown')}"
        )
        return
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("✅ Supabase client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Could not initialize Supabase client: {e}")

def get_supabase() -> Optional[Client]:
    if not supabase:
        init_db()
    return supabase

def get_db():
    yield get_supabase()

