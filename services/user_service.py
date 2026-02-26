from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from core.database import get_supabase
from core.security import get_password_hash, verify_password
from datetime import datetime

class UserService:
    @staticmethod
    def _get_db():
        supabase = get_supabase()
        if not supabase:
            raise HTTPException(status_code=500, detail="Database error")
        return supabase

    @classmethod
    def get_user_by_mobile(cls, mobile: str) -> Optional[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("users").select("*").eq("mobile", mobile).execute()
        return result.data[0] if result.data else None

    @classmethod
    def register_user(cls, user_data: Dict[str, Any]) -> Dict[str, Any]:
        supabase = cls._get_db()
        
        # Check existing
        if cls.get_user_by_mobile(user_data["mobile"]):
            raise HTTPException(status_code=400, detail="Mobile already registered")
            
        # Insert
        user_data["password_hash"] = get_password_hash(user_data.pop("password"))
        user_data["is_active"] = True
        user_data["token_version"] = 1
        
        result = supabase.table("users").insert(user_data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create user")
            
        user = result.data[0]
        user.pop("password_hash", None)
        return user

    @classmethod
    def authenticate_user(cls, mobile: str, password: str) -> Optional[Dict[str, Any]]:
        user = cls.get_user_by_mobile(mobile)
        if not user or not user.get("is_active"):
            return None
        if not verify_password(password, user["password_hash"]):
            return None
            
        # Update last login
        supabase = cls._get_db()
        supabase.table("users").update({"last_login_at": datetime.now().isoformat()}).eq("id", user["id"]).execute()
        
        user.pop("password_hash", None)
        return user

    @classmethod
    def revoke_token(cls, token: str, expires_at: datetime):
        supabase = cls._get_db()
        supabase.table("token_blacklist").insert({
            "token": token,
            "expires_at": expires_at.isoformat()
        }).execute()
        
    @classmethod
    def increment_token_version(cls, user_id: int):
        supabase = cls._get_db()
        result = supabase.rpc('increment_token_version', {"user_id_param": user_id}).execute()
        # Fallback to direct update if RPC not present:
        if not result.data:
            user = supabase.table("users").select("token_version").eq("id", user_id).execute().data[0]
            new_v = (user.get("token_version") or 1) + 1
            supabase.table("users").update({"token_version": new_v}).eq("id", user_id).execute()
