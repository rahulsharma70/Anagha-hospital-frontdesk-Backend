"""
Authentication module using Supabase (shared with mobile project)
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from database import get_supabase
import config  # This will be config_web or config_mobile depending on which server loaded it

# Security configuration (shared with mobile project)
SECRET_KEY = config.JWT_SECRET
ALGORITHM = config.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.JWT_EXPIRATION_HOURS * 60  # Convert hours to minutes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash (using bcrypt like mobile project)"""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Hash a password (using bcrypt like mobile project)"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token (shared with mobile project)"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def authenticate_user(mobile: str, password: str):
    """Authenticate user by mobile and password (using Supabase)"""
    supabase = get_supabase()
    if not supabase:
        return False
    
    try:
        result = supabase.table("users").select("*").eq("mobile", mobile).eq("is_active", True).execute()
        if not result.data:
            return False
        
        user = result.data[0]
        if not verify_password(password, user["password_hash"]):
            return False
        return user
    except Exception:
        return False

async def get_current_user(
    token: str = Depends(oauth2_scheme)
):
    """Get current authenticated user from token (using Supabase)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    supabase = get_supabase()
    if not supabase:
        raise credentials_exception
    
    try:
        result = supabase.table("users").select("*").eq("id", int(user_id)).execute()
        if not result.data:
            raise credentials_exception
        return result.data[0]
    except Exception:
        raise credentials_exception

async def get_current_doctor(
    current_user: dict = Depends(get_current_user)
):
    """Ensure current user is a doctor"""
    if current_user.get("role") != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor access required"
        )
    return current_user

