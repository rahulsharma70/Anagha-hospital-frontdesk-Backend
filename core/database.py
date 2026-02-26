from supabase import create_client, Client
from typing import Optional
from core.config import settings

supabase: Optional[Client] = None

def init_db():
    global supabase
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            print("✅ Supabase client initialized securely in core/database.py")
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Supabase client: {e}")

def get_supabase() -> Optional[Client]:
    if not supabase:
        init_db()
    return supabase

def get_db():
    yield get_supabase()
