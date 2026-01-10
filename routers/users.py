from fastapi import APIRouter, Depends, HTTPException, status, Request, Security
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import get_supabase
from schemas import UserCreate, UserLogin, UserResponse, Token
from auth import (
    authenticate_user, create_access_token, get_current_user,
    get_password_hash, get_current_doctor
)
from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import Optional
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
            # Doctors are NOT stored in users table - only patients and pharma
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor registration must use /api/users/register-doctor endpoint"
            )
        
        # Insert user (only patients and pharma)
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

security = HTTPBearer(auto_error=False)

def get_optional_doctor(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    """Optional dependency to get current doctor if authenticated, else None"""
    if not credentials:
        return None
    
    try:
        # Decode token to get user_id
        token = credentials.credentials
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        user_id = payload.get("sub")
        
        if user_id:
            # Try to get the doctor profile for the authenticated user
            supabase = get_supabase()
            if supabase:
                doctor_result = supabase.table("doctors").select("*").eq("user_id", int(user_id)).eq("is_active", True).execute()
                if doctor_result.data:
                    doctor = doctor_result.data[0]
                    doctor["user_id"] = int(user_id)  # Add user_id for compatibility
                    return doctor
    except (JWTError, Exception):
        pass  # Not authenticated or not a doctor - continue without admin_doctor
    return None

@router.post("/register-doctor", response_model=dict)
def register_doctor(
    user: UserCreate,
    admin_doctor: Optional[dict] = Depends(get_optional_doctor)  # Optional - get current doctor if authenticated
):
    """Register a new doctor - creates both user (auth) and doctor (profile) records
    Supports both:
    - Option 1: Auto-assign hospital from registering doctor's hospital (if authenticated as doctor)
    - Option 2: Explicit hospital_id override (if provided in request - overrides Option 1)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("🔵 DEBUG: Doctor Registration Started")
    logger.info("=" * 60)
    logger.info(f"🔵 DEBUG: Received user data - name: {user.name}, mobile: {user.mobile}, role: {getattr(user.role, 'value', user.role)}")
    logger.info(f"🔵 DEBUG: Hospital ID from request: {user.hospital_id}")
    logger.info(f"🔵 DEBUG: Admin doctor (if authenticated): {admin_doctor}")
    logger.info(f"🔵 DEBUG: Degree: {user.degree}, Institute: {user.institute_name}")
    
    supabase = get_supabase()
    if not supabase:
        logger.error("❌ DEBUG: Database not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Validate required doctor fields
        logger.info("🔵 DEBUG: Validating required fields...")
        if not user.degree:
            logger.error("❌ DEBUG: Degree missing")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Degree is required for doctor registration"
            )
        if not user.institute_name:
            logger.error("❌ DEBUG: Institute name missing")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Institute name is required for doctor registration"
            )
        logger.info("✅ DEBUG: Required fields validated")
        
        # Check if mobile already exists in users table
        existing_user = supabase.table("users").select("id").eq("mobile", user.mobile).execute()
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered"
            )
        
        # Check if mobile already exists in doctors table
        existing_doctor = supabase.table("doctors").select("id").eq("mobile", user.mobile).execute()
        if existing_doctor.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered as a doctor"
            )
        
        # Determine hospital_id using both options:
        # Option 1: Auto-assign from registering doctor's hospital (if authenticated as doctor)
        # Option 2: Use explicit hospital_id from request (overrides Option 1 if provided)
        hospital_id = None
        
        logger.info("🔵 DEBUG: Determining hospital_id...")
        # Option 1: Try to get registering doctor's hospital_id (if authenticated as doctor)
        if admin_doctor and admin_doctor.get("hospital_id"):
            hospital_id = admin_doctor["hospital_id"]
            logger.info(f"🔵 DEBUG: Option 1 - Using admin doctor's hospital_id: {hospital_id}")
        
        # Option 2: Use explicit hospital_id from request (overrides Option 1 if provided)
        if user.hospital_id:
            hospital_id = user.hospital_id
            logger.info(f"🔵 DEBUG: Option 2 - Using explicit hospital_id from request: {hospital_id}")
        
        # Validate that we have a hospital_id
        if not hospital_id:
            logger.error("❌ DEBUG: No hospital_id found - neither from admin doctor nor request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hospital ID is required. Either provide hospital_id in request or register as an authenticated doctor."
            )
        logger.info(f"✅ DEBUG: Using hospital_id: {hospital_id}")
        
        # Verify hospital exists and is approved
        logger.info(f"🔵 DEBUG: Verifying hospital ID {hospital_id} exists and is approved...")
        hospital_result = supabase.table("hospitals").select("id, name, status").eq("id", hospital_id).execute()
        if not hospital_result.data:
            logger.error(f"❌ DEBUG: Hospital ID {hospital_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        hospital = hospital_result.data[0]
        logger.info(f"🔵 DEBUG: Hospital found - name: {hospital.get('name')}, status: {hospital.get('status')}")
        if hospital.get("status") != "approved":
            logger.error(f"❌ DEBUG: Hospital status is {hospital.get('status')}, not approved")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot register doctor with unapproved hospital"
            )
        logger.info("✅ DEBUG: Hospital verified and approved")
        
        # Step 1: Create user record for authentication (with a dummy role, since doctors don't use users table for profile)
        # Actually, we'll create a minimal user record just for auth, but doctors won't have role='doctor' in users table
        # For now, let's create a users entry with a placeholder role (we'll link via user_id in doctors table)
        logger.info("🔵 DEBUG: Step 1 - Creating user record for authentication...")
        user_record = {
            "name": user.name,
            "mobile": user.mobile,
            "role": "patient",  # Temporary role, actual doctor info is in doctors table
            "password_hash": get_password_hash(user.password),
            "is_active": True,
        }
        
        # Add optional address fields
        if user.address_line1:
            user_record["address_line1"] = user.address_line1
        if user.address_line2:
            user_record["address_line2"] = user.address_line2
        if user.address_line3:
            user_record["address_line3"] = user.address_line3
        
        logger.info(f"🔵 DEBUG: Inserting user record: {user_record}")
        user_result = supabase.table("users").insert(user_record).execute()
        if not user_result.data:
            logger.error("❌ DEBUG: Failed to insert user record")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
        db_user = user_result.data[0]
        user_id = db_user["id"]
        logger.info(f"✅ DEBUG: User record created with ID: {user_id}")
        
        # Step 2: Create doctor record in doctors table
        logger.info("🔵 DEBUG: Step 2 - Creating doctor record in doctors table...")
        doctor_record = {
            "user_id": user_id,  # Link to users table for authentication
            "hospital_id": hospital_id,  # Use determined hospital_id (from Option 1 or Option 2)
            "name": user.name,
            "mobile": user.mobile,
            "email": user.email,
            "degree": user.degree,  # Required
            "institute_name": user.institute_name,  # Required
            "specialization": None,  # Can be set later
            "experience1": user.experience1,
            "experience2": user.experience2,
            "experience3": user.experience3,
            "experience4": user.experience4,
            "is_active": True,
            "source": "registered"
        }
        
        logger.info(f"🔵 DEBUG: Inserting doctor record: {doctor_record}")
        doctor_result = supabase.table("doctors").insert(doctor_record).execute()
        if not doctor_result.data:
            logger.error("❌ DEBUG: Failed to insert doctor record, rolling back user...")
            # Rollback: delete the user record we just created
            try:
                supabase.table("users").delete().eq("id", user_id).execute()
                logger.info("✅ DEBUG: User record rolled back")
            except Exception as rollback_error:
                logger.error(f"❌ DEBUG: Rollback failed: {rollback_error}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create doctor profile"
            )
        
        db_doctor = doctor_result.data[0]
        db_user.pop("password_hash", None)
        logger.info(f"✅ DEBUG: Doctor record created with ID: {db_doctor['id']}")
        
        # Return combined doctor info
        result = {
            "id": db_doctor["id"],  # Doctor ID (primary identifier)
            "user_id": user_id,  # User ID for authentication
            "name": db_doctor["name"],
            "mobile": db_doctor["mobile"],
            "hospital_id": db_doctor["hospital_id"],
            "degree": db_doctor["degree"],
            "institute_name": db_doctor["institute_name"],
            "specialization": db_doctor.get("specialization"),
            "is_active": db_doctor["is_active"]
        }
        logger.info("=" * 60)
        logger.info(f"✅ DEBUG: Doctor Registration SUCCESS - Doctor ID: {db_doctor['id']}, User ID: {user_id}")
        logger.info("=" * 60)
        return result
    except HTTPException as he:
        logger.error(f"❌ DEBUG: HTTPException - {he.status_code}: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ DEBUG: Unexpected error: {str(e)}", exc_info=True)
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
        result = supabase.table("doctors").select("id, name, mobile, degree, institute_name, specialization, hospital_id").eq("is_active", True).execute()
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
        result = supabase.table("doctors").select("id, name, mobile, degree, institute_name, specialization, hospital_id").eq("is_active", True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching doctors: {e}")
        return []

@router.patch("/doctors/{doctor_id}/hospital")
def update_doctor_hospital(
    doctor_id: int,
    hospital_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Update a doctor's hospital association. Requires authentication."""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Verify doctor exists in doctors table
        doctor_result = supabase.table("doctors").select("*").eq("id", doctor_id).eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        
        # Verify hospital exists
        hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        # Update doctor's hospital_id in doctors table
        update_result = supabase.table("doctors").update({"hospital_id": hospital_id}).eq("id", doctor_id).execute()
        
        if update_result.data:
            return {
                "message": "Doctor hospital updated successfully",
                "doctor_id": doctor_id,
                "hospital_id": hospital_id,
                "hospital_name": hospital_result.data[0].get("name", "")
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update doctor hospital"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating doctor hospital: {str(e)}"
        )
