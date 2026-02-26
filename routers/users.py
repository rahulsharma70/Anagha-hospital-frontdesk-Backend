from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from dependencies.auth import get_current_user, get_current_doctor, get_current_active_user
from services.user_service import UserService
from services.doctor_service import DoctorService
from schemas import UserCreate, UserLogin, UserResponse
from core.security import create_access_token, create_refresh_token
from services.audit_logger import log_login_attempt
from fastapi_limiter.depends import RateLimiter
from core.limiter import get_real_ip
from typing import Optional

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/register", response_model=dict, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def register_user(user: UserCreate, response: Response):
    """Register a new patient or pharma user"""
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    if role_str == "doctor":
        raise HTTPException(status_code=400, detail="Use /register-doctor endpoint")

    user_data = user.model_dump(exclude_unset=True)
    user_data["role"] = role_str
    
    # Address handling
    if hasattr(user, 'address') and user.address and not user_data.get("address_line1"):
        user_data["address_line1"] = user.address
    user_data.pop("address", None)
        
    db_user = UserService.register_user(user_data)
    
    access_token = create_access_token(data={"sub": str(db_user["id"]), "role": db_user["role"], "token_version": 1})
    refresh_token = create_refresh_token(data={"sub": str(db_user["id"]), "role": db_user["role"], "token_version": 1})
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="lax", max_age=86400)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="lax", max_age=604800)
    
    return {
        "user": db_user,
        "message": "User registered successfully"
    }

@router.post("/login", response_model=dict, dependencies=[Depends(RateLimiter(times=5, seconds=300))])
async def login_user(user_credentials: UserLogin, request: Request, response: Response, ip: str = Depends(get_real_ip)):
    """Login user with brute-force protection"""
    user_agent = request.headers.get("user-agent")
    
    user = UserService.authenticate_user(user_credentials.mobile, user_credentials.password)
    if not user:
        log_login_attempt(mobile=user_credentials.mobile, success=False, ip_address=ip, user_agent=user_agent)
        raise HTTPException(status_code=401, detail="Incorrect credentials")
        
    log_login_attempt(mobile=user_credentials.mobile, user_id=user["id"], success=True, ip_address=ip, user_agent=user_agent)
    
    token_version = user.get("token_version", 1)
    
    access_token = create_access_token(data={"sub": str(user["id"]), "role": user["role"], "token_version": token_version})
    refresh_token = create_refresh_token(data={"sub": str(user["id"]), "role": user["role"], "token_version": token_version})
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="lax", max_age=86400)
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="lax", max_age=604800)
    
    return {
        "user": user,
        "message": "Login successful"
    }

@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    current_user.pop("password_hash", None)
    return current_user

@router.post("/register-doctor", response_model=dict, dependencies=[Depends(RateLimiter(times=3, seconds=60))])
async def register_doctor(user: UserCreate):
    """Registers a doctor and marks them as PENDING_APPROVAL"""
    if not user.degree or not user.institute_name or not user.hospital_id:
        raise HTTPException(status_code=400, detail="Degree, Institute, and Hospital ID are required")
        
    user_data = {
        "name": user.name,
        "mobile": user.mobile,
        "role": "patient", # Temporary role for auth
        "password": user.password,
    }
    
    doctor_data = {
        "hospital_id": user.hospital_id,
        "name": user.name,
        "mobile": user.mobile,
        "email": user.email,
        "degree": user.degree,
        "institute_name": user.institute_name,
        "experience1": user.experience1,
        "source": "registered"
    }
    
    # Needs to hash password first
    from core.security import get_password_hash
    user_data["password_hash"] = get_password_hash(user_data.pop("password"))
    user_data["is_active"] = True
    user_data["token_version"] = 1
    
    doc = DoctorService.register_doctor(doctor_data, user_data)
    return doc

@router.get("/doctors")
async def get_all_doctors(current_user: dict = Depends(get_current_user)):
    """Doctors list endpoint"""
    return DoctorService.get_public_doctors()

@router.get("/doctors/public")
async def get_all_doctors_public(q: Optional[str] = None):
    return DoctorService.get_public_doctors(q)

@router.get("/doctors/search")
async def search_doctors(q: Optional[str] = None):
    return DoctorService.get_public_doctors(q)

@router.get("/cities/search")
async def search_cities(q: Optional[str] = None):
    return DoctorService.get_cities()
