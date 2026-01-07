from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from database import get_supabase
from schemas import UserCreate, UserLogin, UserResponse, Token
from auth import (
    authenticate_user, create_access_token, get_current_user,
    get_password_hash, get_current_doctor
)
from datetime import datetime, timedelta
import config
from services.audit_logger import log_login_attempt

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("/register", response_model=dict)
def register_user(user: UserCreate):
    """Register a new user (patient or pharma or doctor) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if mobile already exists
        existing = supabase.table("users").select("id").eq("mobile", user.mobile).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered"
            )
        
        # Get role as string
        role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
        
        # Prepare user record for Supabase
        # Handle 'address' field from frontend (convert to address_line1)
        address_line1 = user.address_line1
        if not address_line1 and hasattr(user, 'address') and user.address:
            address_line1 = user.address
        
        # Prepare user record for Supabase - only include fields with values
        user_record = {
            "name": user.name,
            "mobile": user.mobile,
            "role": role_str,
            "password_hash": get_password_hash(user.password),
            "is_active": True,
        }
        
        # Add optional fields only if they have values
        if address_line1:
            user_record["address_line1"] = address_line1
        if user.address_line2:
            user_record["address_line2"] = user.address_line2
        if user.address_line3:
            user_record["address_line3"] = user.address_line3
        if user.hospital_id:
            user_record["hospital_id"] = user.hospital_id
        
        # Add role-specific fields only if they have values
        if role_str == "pharma":
            if user.company_name:
                user_record["company_name"] = user.company_name
            if user.product1:
                user_record["product1"] = user.product1
            if user.product2:
                user_record["product2"] = user.product2
            if user.product3:
                user_record["product3"] = user.product3
            if user.product4:
                user_record["product4"] = user.product4
        elif role_str == "doctor":
            if user.degree:
                user_record["degree"] = user.degree
            if user.institute_name:
                user_record["institute_name"] = user.institute_name
            if user.experience1:
                user_record["experience1"] = user.experience1
            if user.experience2:
                user_record["experience2"] = user.experience2
            if user.experience3:
                user_record["experience3"] = user.experience3
            if user.experience4:
                user_record["experience4"] = user.experience4
        
        # Insert user
        result = supabase.table("users").insert(user_record).execute()
        if result.data:
            db_user = result.data[0]
            # Remove password hash from response
            db_user.pop("password_hash", None)
            access_token = create_access_token(data={"sub": str(db_user["id"]), "role": db_user["role"]})
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": db_user,
                "message": "User registered successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register user"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {str(e)}"
        )

@router.post("/login", response_model=dict)
def login_user(user_credentials: UserLogin, request: Request):
    """Login user and return access token - using Supabase"""
    user = authenticate_user(user_credentials.mobile, user_credentials.password)
    
    # Get client IP and user agent for audit logging
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    if not user:
        # Log failed login attempt
        log_login_attempt(
            mobile=user_credentials.mobile,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
            error_message="Incorrect mobile number or password"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Log successful login attempt
    log_login_attempt(
        mobile=user_credentials.mobile,
        user_id=user["id"],
        success=True,
        ip_address=client_ip,
        user_agent=user_agent
    )
    
    supabase = get_supabase()
    if supabase:
        # Update last login
        try:
            supabase.table("users").update({
                "last_login_at": datetime.now().isoformat()
            }).eq("id", user["id"]).execute()
        except:
            pass  # Don't fail if update fails
    
    access_token_expires = timedelta(hours=config.JWT_EXPIRATION_HOURS)
    access_token = create_access_token(
        data={"sub": str(user["id"]), "role": user["role"]}, expires_delta=access_token_expires
    )
    
    # Remove password hash
    user.pop("password_hash", None)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=dict)
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information - using Supabase"""
    # Remove password hash
    current_user.pop("password_hash", None)
    return current_user

@router.post("/register-doctor", response_model=dict)
def register_doctor(
    user: UserCreate,
    admin_user: dict = Depends(get_current_doctor)
):
    """Register a new doctor (only accessible by existing doctors) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if mobile already exists
        existing = supabase.table("users").select("id").eq("mobile", user.mobile).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered"
            )
        
        # Create new doctor
        user_record = {
            "name": user.name,
            "mobile": user.mobile,
            "role": "doctor",
            "password_hash": get_password_hash(user.password),
            "address_line1": user.address_line1,
            "address_line2": user.address_line2,
            "address_line3": user.address_line3,
            "hospital_id": user.hospital_id,
            "degree": user.degree,
            "institute_name": user.institute_name,
            "experience1": user.experience1,
            "experience2": user.experience2,
            "experience3": user.experience3,
            "experience4": user.experience4,
            "is_active": True
        }
        
        result = supabase.table("users").insert(user_record).execute()
        if result.data:
            db_user = result.data[0]
            db_user.pop("password_hash", None)
            return db_user
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register doctor"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering doctor: {str(e)}"
        )

@router.get("/doctors")
def get_all_doctors(current_user: dict = Depends(get_current_user)):
    """Get list of all registered doctors - using Supabase. Requires authentication."""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("users").select("id, name, mobile, degree, institute_name").eq("role", "doctor").eq("is_active", True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        return []

@router.get("/doctors/public")
def get_all_doctors_public():
    """Get list of all registered doctors - public endpoint for booking pages. No authentication required."""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("users").select("id, name, mobile, degree, institute_name, hospital_id").eq("role", "doctor").eq("is_active", True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        return []
