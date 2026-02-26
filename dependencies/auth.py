from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from core.config import settings
from core.database import get_supabase
from typing import Optional

async def get_current_user(request: Request):
    """Get current authenticated user from HttpOnly cookie or Authorization header"""
    token = request.cookies.get("access_token")
    
    # Fallback to Authorization header (for mobile/API clients)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    
    if not token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        token_version = payload.get("token_version")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    supabase = get_supabase()
    if not supabase:
        raise HTTPException(status_code=500, detail="Database error")
    
    # 1. Check if token is blacklisted
    is_blacklisted = supabase.table("token_blacklist").select("id").eq("token", token).execute()
    if is_blacklisted.data:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    # 2. Fetch user
    result = supabase.table("users").select("*").eq("id", int(user_id)).execute()
    if not result.data:
        raise credentials_exception
        
    user = result.data[0]
    
    # 3. Check is_active flag
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Inactive user account")
        
    # 4. Check token_version
    # Only enforce if token_version is present in DB and Payload
    db_token_version = user.get("token_version")
    if db_token_version is not None and token_version is not None:
        if int(db_token_version) != int(token_version):
            raise HTTPException(status_code=401, detail="Token is no longer valid (password changed or sessions revoked)")

    return user

async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    return current_user

async def get_current_doctor(current_user: dict = Depends(get_current_user)):
    """Ensure current user is a doctor and return doctor profile"""
    supabase = get_supabase()
    
    try:
        doctor_result = supabase.table("doctors").select("*").eq("user_id", current_user["id"]).eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor access required. No active doctor profile found."
            )
            
        doctor = doctor_result.data[0]
        # Merge info for compatibility mapping
        doctor["user_id"] = current_user["id"]
        doctor["role"] = "doctor"
        doctor["name"] = doctor.get("name", current_user.get("name", ""))
        return doctor
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=403, detail=f"Error verifying doctor access: {str(e)}")

async def get_current_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
