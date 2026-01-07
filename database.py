"""
Database configuration using Supabase (shared with mobile project)
"""
import os
from typing import Optional
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

# Supabase Configuration (shared with mobile project)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Optional[object] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized successfully (shared with mobile)")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize Supabase client: {e}")
        print("⚠️ Server will continue with in-memory storage as fallback")
        supabase = None
else:
    print("⚠️ Warning: SUPABASE_URL or SUPABASE_KEY not found in .env")
    print("⚠️ Server will continue with in-memory storage as fallback")
    supabase = None

def get_db():
    """Dependency to get Supabase client (for compatibility with existing code)"""
    # Return supabase client instead of SQLAlchemy session
    # This maintains compatibility with dependency injection pattern
    yield supabase

def get_supabase():
    """Get Supabase client directly"""
    return supabase

def init_db():
    """Initialize database (Supabase tables should already exist)"""
    if supabase:
        try:
            # Test connection by querying a table
            supabase.table("hospitals").select("id").limit(1).execute()
            print("✅ Database connection verified")
        except Exception as e:
            print(f"⚠️ Warning: Database connection test failed: {e}")
    else:
        print("⚠️ Supabase not configured, skipping database initialization")

