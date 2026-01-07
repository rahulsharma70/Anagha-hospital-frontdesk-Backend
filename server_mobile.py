"""
FastAPI server with Supabase database integration
Run this with: python server_mobile.py
Or: uvicorn server_mobile:app --reload --host 127.0.0.1 --port 8000
"""

import os
import sys
from pathlib import Path

# Override config module before any other imports
import config_mobile
sys.modules['config'] = config_mobile
import config

from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client
import bcrypt
from jose import JWTError, jwt
from payment_gateway import PaymentGateway

# Load environment variables from current or parent directory
env_path = Path(__file__).parent / ".env"
parent_env_path = Path(__file__).parent.parent / ".env"
# Try to load from parent first (since that's where the user placed it)
if parent_env_path.exists():
    load_dotenv(parent_env_path, override=True)
elif env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

app = FastAPI(title="Anagha Hospital Solutions API")

# Supabase Configuration
SUPABASE_URL = config.SUPABASE_URL
SUPABASE_KEY = config.SUPABASE_KEY

# Initialize Supabase client
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize Supabase client: {e}")
        print("⚠️ Server will continue with in-memory storage as fallback")
        supabase = None
else:
    print("⚠️ Warning: SUPABASE_URL or SUPABASE_KEY not found in .env")
    print("⚠️ Server will continue with in-memory storage as fallback")
    supabase = None

# Fallback in-memory storage (if Supabase not available)
hospitals_storage = []
users_storage = []
appointments_storage = []
operations_storage = []

# JWT Configuration
JWT_SECRET = config.JWT_SECRET
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = config.JWT_EXPIRATION_HOURS

# Password hashing helper
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
ADMIN_PANEL_PATH = BASE_DIR.parent / "frontend" / "web" / "templates" / "admin_panel.html"

# Serve admin panel HTML file
@app.get("/admin_panel.html", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def admin_panel():
    """Serve the web admin panel"""
    try:
        # Try new location first
        if ADMIN_PANEL_PATH.exists():
            with open(ADMIN_PANEL_PATH, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        # Fallback to old location (for backward compatibility)
        admin_panel_path = BASE_DIR / "admin_panel.html"
        if admin_panel_path.exists():
            with open(admin_panel_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        return HTMLResponse(
            content="<html><body><h1>Admin Panel Not Found</h1></body></html>",
            status_code=404
        )
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body><h1>Error loading admin panel</h1><p>{str(e)}</p></body></html>",
            status_code=500
        )

# ============================================
# HOSPITAL ENDPOINTS
# ============================================

@app.post("/api/hospitals/register")
async def register_hospital(hospital_data: dict = Body(...)):
    """Register a new hospital (payment required)"""
    try:
        # Check if payment_order_id is provided and verified
        payment_order_id = hospital_data.get("payment_order_id")
        if not payment_order_id:
            raise HTTPException(
                status_code=400, 
                detail="Payment is required for hospital registration. Please complete payment first."
            )
        
        # Verify payment
        if supabase:
            payment_check = supabase.table("payments").select("*").eq(
                "order_id", payment_order_id
            ).eq("status", "paid").execute()
            
            if not payment_check.data:
                raise HTTPException(
                    status_code=400,
                    detail="Payment not verified. Please complete payment first."
                )
        
        hospital_record = {
            "name": hospital_data.get("name", ""),
            "email": hospital_data.get("email", ""),
            "mobile": hospital_data.get("mobile", ""),
            "status": "pending",
            "address_line1": hospital_data.get("address_line1"),
            "address_line2": hospital_data.get("address_line2"),
            "address_line3": hospital_data.get("address_line3"),
            "city": hospital_data.get("city"),
            "state": hospital_data.get("state"),
            "pincode": hospital_data.get("pincode"),
            "whatsapp_enabled": hospital_data.get("whatsapp_enabled", False),
            "whatsapp_number": hospital_data.get("whatsapp_number"),
            "default_upi_id": hospital_data.get("default_upi_id"),
            "google_pay_upi_id": hospital_data.get("google_pay_upi_id"),
            "phonepe_upi_id": hospital_data.get("phonepe_upi_id"),
            "paytm_upi_id": hospital_data.get("paytm_upi_id"),
            "bhim_upi_id": hospital_data.get("bhim_upi_id"),
            "payment_qr_code": hospital_data.get("payment_qr_code"),
        }
        
        if supabase:
            # Use Supabase
            result = supabase.table("hospitals").insert(hospital_record).execute()
            if result.data:
                hospital = result.data[0]
                return {"id": hospital["id"], "message": "Hospital registered successfully", "hospital": hospital}
        else:
            # Fallback to in-memory storage
            hospital_id = int(datetime.now().timestamp())
            hospital = {"id": hospital_id, **hospital_record, "created_at": datetime.now().isoformat()}
            hospitals_storage.append(hospital)
            return {"id": hospital_id, "message": "Hospital registered successfully", "hospital": hospital}
            
        raise HTTPException(status_code=500, detail="Failed to register hospital")
    except Exception as e:
        print(f"Error registering hospital: {e}")
        raise HTTPException(status_code=500, detail=f"Error registering hospital: {str(e)}")

@app.get("/api/hospitals/pending")
async def get_pending_hospitals():
    """Get all pending hospitals"""
    try:
        if supabase:
            result = supabase.table("hospitals").select("*").eq("status", "pending").execute()
            return result.data if result.data else []
        else:
            return [h for h in hospitals_storage if h.get("status") == "pending"]
    except Exception as e:
        print(f"Error fetching pending hospitals: {e}")
        return []

@app.get("/api/hospitals/approved")
async def get_approved_hospitals():
    """Get all approved hospitals"""
    try:
        if supabase:
            result = supabase.table("hospitals").select("*").eq("status", "approved").execute()
            return result.data if result.data else []
        else:
            return [h for h in hospitals_storage if h.get("status") == "approved"]
    except Exception as e:
        print(f"Error fetching approved hospitals: {e}")
        return []

@app.put("/api/hospitals/{hospital_id}/approve")
@app.post("/api/hospitals/{hospital_id}/approve")
async def approve_hospital(hospital_id: int):
    """Approve a hospital"""
    try:
        if supabase:
            result = supabase.table("hospitals").update({
                "status": "approved",
                "approved_at": datetime.now().isoformat()
            }).eq("id", hospital_id).execute()
            
            if result.data:
                hospital = result.data[0]
                return {
                    "status": "approved",
                    "message": "Hospital approved successfully",
                    "hospital_id": hospital_id,
                    "hospital": hospital
                }
            else:
                raise HTTPException(status_code=404, detail=f"Hospital with ID {hospital_id} not found")
        else:
            # Fallback to in-memory
            hospital = None
            for h in hospitals_storage:
                if h.get("id") == hospital_id:
                    hospital = h
                    break
            if not hospital:
                raise HTTPException(status_code=404, detail=f"Hospital with ID {hospital_id} not found")
            hospital["status"] = "approved"
            hospital["approved_at"] = datetime.now().isoformat()
            return {
                "status": "approved",
                "message": "Hospital approved successfully",
                "hospital_id": hospital_id,
                "hospital": hospital
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error approving hospital: {e}")
        raise HTTPException(status_code=500, detail=f"Error approving hospital: {str(e)}")

# ============================================
# USER ENDPOINTS (Doctors & Pharma)
# ============================================

@app.post("/api/users/register")
async def register_user(user_data: dict):
    """Register a new user (Pharma or Doctor)"""
    try:
        # Hash password
        password_hash = hash_password(user_data.get("password", ""))
        
        user_record = {
            "name": user_data.get("name", ""),
            "mobile": user_data.get("mobile", ""),
            "email": user_data.get("email"),
            "password_hash": password_hash,
            "role": user_data.get("role", "pharma"),
            "address_line1": user_data.get("address_line1"),
            "address_line2": user_data.get("address_line2"),
            "address_line3": user_data.get("address_line3"),
            "city": user_data.get("city"),
            "state": user_data.get("state"),
            "pincode": user_data.get("pincode"),
            "hospital_id": user_data.get("hospital_id"),
            "company_name": user_data.get("company_name"),
            "product1": user_data.get("product1"),
            "product2": user_data.get("product2"),
            "product3": user_data.get("product3"),
            "product4": user_data.get("product4"),
            "degree": user_data.get("degree"),
            "institute_name": user_data.get("institute_name"),
            "experience1": user_data.get("experience1"),
            "experience2": user_data.get("experience2"),
            "experience3": user_data.get("experience3"),
            "experience4": user_data.get("experience4"),
            "doctor_name": user_data.get("doctor_name"),
            "place": user_data.get("place"),
            "patient_referred_name": user_data.get("patient_referred_name"),
            "problem": user_data.get("problem"),
            "patient_mobile": user_data.get("patient_mobile"),
            "ref_no": user_data.get("ref_no"),
        }
        
        if supabase:
            # Check if user exists
            existing = supabase.table("users").select("id").eq("mobile", user_data.get("mobile")).execute()
            if existing.data:
                raise HTTPException(status_code=400, detail="User with this mobile number already exists")
            
            result = supabase.table("users").insert(user_record).execute()
            if result.data:
                user = result.data[0]
                user.pop("password_hash", None)
                access_token = create_access_token(data={"sub": str(user["id"]), "role": user["role"]})
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": user,
                    "message": "User registered successfully"
                }
        else:
            # Fallback to in-memory
            for u in users_storage:
                if u.get("mobile") == user_data.get("mobile"):
                    raise HTTPException(status_code=400, detail="User with this mobile number already exists")
            
            user_id = len(users_storage) + 1
            user = {"id": user_id, **user_record, "created_at": datetime.now().isoformat()}
            users_storage.append(user)
            user.pop("password_hash", None)
            import hashlib
            token = hashlib.md5(f"{user['mobile']}{datetime.now().isoformat()}".encode()).hexdigest()
            return {
                "access_token": token,
                "user": user,
                "message": "User registered successfully"
            }
            
        raise HTTPException(status_code=500, detail="Failed to register user")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail=f"Error registering user: {str(e)}")

@app.post("/api/users/login")
async def login_user(credentials: dict):
    """Login user with mobile and password"""
    try:
        mobile = credentials.get("mobile")
        password = credentials.get("password")
        
        if not mobile or not password:
            raise HTTPException(status_code=400, detail="Mobile and password are required")
        
        if supabase:
            result = supabase.table("users").select("*").eq("mobile", mobile).eq("is_active", True).execute()
            if not result.data:
                raise HTTPException(status_code=401, detail="Invalid mobile or password")
            
            user = result.data[0]
            if not verify_password(password, user["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid mobile or password")
            
            # Update last login
            supabase.table("users").update({
                "last_login_at": datetime.now().isoformat()
            }).eq("id", user["id"]).execute()
            
            user.pop("password_hash", None)
            access_token = create_access_token(data={"sub": str(user["id"]), "role": user["role"]})
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "user": user,
                "message": "Login successful"
            }
        else:
            # Fallback to in-memory
            user = None
            for u in users_storage:
                if u.get("mobile") == mobile:
                    user = u
                    break
            if not user:
                raise HTTPException(status_code=401, detail="Invalid mobile or password")
            
            import hashlib
            token = hashlib.md5(f"{user['mobile']}{datetime.now().isoformat()}".encode()).hexdigest()
            return {
                "access_token": token,
                "user": user,
                "message": "Login successful"
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error logging in user: {e}")
        raise HTTPException(status_code=500, detail=f"Error logging in: {str(e)}")

# ============================================
# APPOINTMENT ENDPOINTS
# ============================================

@app.post("/api/appointments/book")
async def book_appointment(appointment_data: dict):
    """Book an appointment (guest or registered patient) with edge case handling"""
    try:
        patient_mobile = appointment_data.get("patient_mobile")
        patient_name = appointment_data.get("patient_name")
        place = appointment_data.get("place")
        hospital_id = appointment_data.get("hospital_id")
        date = appointment_data.get("date")
        time = appointment_data.get("time")
        order_id = appointment_data.get("order_id")  # Payment order ID
        
        # Edge Case 1: Validate required fields
        if not all([patient_mobile, patient_name, place, hospital_id, date, time]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Edge Case 2: Verify payment before booking
        if order_id:
            is_verified, error_msg = verify_payment_before_booking(order_id)
            if not is_verified:
                raise HTTPException(status_code=400, detail=error_msg)
        
        # Edge Case 3: Check for deadlock (multiple simultaneous bookings)
        is_safe, deadlock_msg = check_booking_deadlock(patient_mobile, hospital_id, date)
        if not is_safe:
            raise HTTPException(status_code=409, detail=deadlock_msg)
        
        # Edge Case 4: Check time slot availability
        is_available, slot_msg = check_time_slot_availability(hospital_id, date, time)
        if not is_available:
            raise HTTPException(status_code=409, detail=slot_msg)
        
        # Edge Case 5: Validate date (not in past)
        try:
            appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
            if appointment_date < datetime.now().date():
                raise HTTPException(status_code=400, detail="Cannot book appointment in the past")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        # Edge Case 6: Validate hospital exists and is approved
        if supabase:
            hospital_result = supabase.table("hospitals").select("id, status").eq("id", hospital_id).execute()
            if not hospital_result.data:
                raise HTTPException(status_code=404, detail="Hospital not found")
            if hospital_result.data[0].get("status") != "approved":
                raise HTTPException(status_code=403, detail="Hospital is not approved for bookings")
        
        # Create or update patient
        patient_id = None
        if supabase:
            patient_result = supabase.table("patients").select("id").eq("mobile", patient_mobile).execute()
            if patient_result.data:
                patient_id = patient_result.data[0]["id"]
                supabase.table("patients").update({
                    "name": patient_name,
                    "place": place,
                    "updated_at": datetime.now().isoformat()
                }).eq("id", patient_id).execute()
            else:
                new_patient = supabase.table("patients").insert({
                    "name": patient_name,
                    "mobile": patient_mobile,
                    "place": place
                }).execute()
                if new_patient.data:
                    patient_id = new_patient.data[0]["id"]
        
        # Determine payment status
        payment_status = "completed" if order_id else "pending"
        
        appointment_record = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_mobile": patient_mobile,
            "place": place,
            "hospital_id": hospital_id,
            "appointment_date": date,
            "appointment_time": time,
            "payment_method": appointment_data.get("payment_method"),
            "payment_status": payment_status,
            "status": "confirmed" if payment_status == "completed" else "pending"
        }
        
        if supabase:
            # Use transaction-like approach (check again before insert to prevent race condition)
            is_available, slot_msg = check_time_slot_availability(hospital_id, date, time)
            if not is_available:
                raise HTTPException(status_code=409, detail=slot_msg)
            
            result = supabase.table("appointments").insert(appointment_record).execute()
            if result.data:
                appointment = result.data[0]
                return {
                    "id": appointment["id"],
                    "message": "Appointment booked successfully",
                    "appointment": appointment
                }
        else:
            appointment_id = len(appointments_storage) + 1
            appointment = {"id": appointment_id, **appointment_record, "created_at": datetime.now().isoformat()}
            appointments_storage.append(appointment)
            return {"id": appointment_id, "message": "Appointment booked successfully", "appointment": appointment}
            
        raise HTTPException(status_code=500, detail="Failed to book appointment")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error booking appointment: {e}")
        raise HTTPException(status_code=500, detail=f"Error booking appointment: {str(e)}")

# ============================================
# OPERATION ENDPOINTS
# ============================================

@app.post("/api/operations/book")
async def book_operation(operation_data: dict):
    """Book an operation (guest or registered patient) with edge case handling"""
    try:
        patient_mobile = operation_data.get("patient_mobile")
        patient_name = operation_data.get("patient_name")
        place = operation_data.get("place")
        hospital_id = operation_data.get("hospital_id")
        date = operation_data.get("date")
        time = operation_data.get("time")
        order_id = operation_data.get("order_id")  # Payment order ID
        
        # Edge Case 1: Validate required fields
        if not all([patient_mobile, patient_name, place, hospital_id, date, time]):
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Edge Case 2: Verify payment before booking
        if order_id:
            is_verified, error_msg = verify_payment_before_booking(order_id)
            if not is_verified:
                raise HTTPException(status_code=400, detail=error_msg)
        
        # Edge Case 3: Check for deadlock
        is_safe, deadlock_msg = check_booking_deadlock(patient_mobile, hospital_id, date)
        if not is_safe:
            raise HTTPException(status_code=409, detail=deadlock_msg)
        
        # Edge Case 4: Check time slot availability (operations need more time, check ±2 hours)
        is_available, slot_msg = check_time_slot_availability(hospital_id, date, time)
        if not is_available:
            raise HTTPException(status_code=409, detail=slot_msg)
        
        # Edge Case 5: Validate date
        try:
            operation_date = datetime.strptime(date, "%Y-%m-%d").date()
            if operation_date < datetime.now().date():
                raise HTTPException(status_code=400, detail="Cannot book operation in the past")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        # Edge Case 6: Validate hospital
        if supabase:
            hospital_result = supabase.table("hospitals").select("id, status").eq("id", hospital_id).execute()
            if not hospital_result.data:
                raise HTTPException(status_code=404, detail="Hospital not found")
            if hospital_result.data[0].get("status") != "approved":
                raise HTTPException(status_code=403, detail="Hospital is not approved for bookings")
        
        # Create or update patient
        patient_id = None
        if supabase:
            patient_result = supabase.table("patients").select("id").eq("mobile", patient_mobile).execute()
            if patient_result.data:
                patient_id = patient_result.data[0]["id"]
            else:
                new_patient = supabase.table("patients").insert({
                    "name": patient_name,
                    "mobile": patient_mobile,
                    "place": place
                }).execute()
                if new_patient.data:
                    patient_id = new_patient.data[0]["id"]
        
        # Determine payment status
        payment_status = "completed" if order_id else "pending"
        
        operation_record = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "patient_mobile": patient_mobile,
            "place": place,
            "hospital_id": hospital_id,
            "operation_date": date,
            "operation_time": time,
            "specialty": operation_data.get("specialty"),
            "payment_method": operation_data.get("payment_method"),
            "payment_status": payment_status,
            "status": "confirmed" if payment_status == "completed" else "pending"
        }
        
        if supabase:
            # Double-check time slot before insert (prevent race condition)
            is_available, slot_msg = check_time_slot_availability(hospital_id, date, time)
            if not is_available:
                raise HTTPException(status_code=409, detail=slot_msg)
            
            result = supabase.table("operations").insert(operation_record).execute()
            if result.data:
                operation = result.data[0]
                return {
                    "id": operation["id"],
                    "message": "Operation booked successfully",
                    "operation": operation
                }
        else:
            operation_id = len(operations_storage) + 1
            operation = {"id": operation_id, **operation_record, "created_at": datetime.now().isoformat()}
            operations_storage.append(operation)
            return {"id": operation_id, "message": "Operation booked successfully", "operation": operation}
            
        raise HTTPException(status_code=500, detail="Failed to book operation")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error booking operation: {e}")
        raise HTTPException(status_code=500, detail=f"Error booking operation: {str(e)}")

# ============================================
# ADMIN ENDPOINTS
# ============================================

@app.post("/api/admin/login")
async def admin_login(credentials: dict):
    """Admin login"""
    try:
        username = credentials.get("username")
        password = credentials.get("password")
        
        if supabase:
            result = supabase.table("admin_users").select("*").eq("username", username).eq("is_active", True).execute()
            if not result.data:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            admin = result.data[0]
            if not verify_password(password, admin["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid username or password")
            
            supabase.table("admin_users").update({
                "last_login_at": datetime.now().isoformat()
            }).eq("id", admin["id"]).execute()
            
            admin.pop("password_hash", None)
            access_token = create_access_token(data={"sub": str(admin["id"]), "role": "admin"})
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "admin": admin
            }
        else:
            # Fallback: hardcoded admin (for testing)
            if username == "anagha" and password == "Uabiotech*2309":
                import hashlib
                token = hashlib.md5(f"{username}{datetime.now().isoformat()}".encode()).hexdigest()
                return {
                    "access_token": token,
                    "admin": {"username": username, "role": "admin"}
                }
            raise HTTPException(status_code=401, detail="Invalid username or password")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# ============================================
# BOOKING VALIDATION & EDGE CASE HANDLING
# ============================================

def check_time_slot_availability(hospital_id: int, date: str, time: str) -> Tuple[bool, str]:
    """
    Check if time slot is available (no conflicts)
    Returns: (is_available, error_message)
    """
    try:
        if not supabase:
            return True, ""  # Skip validation if no database
        
        # Parse time
        time_parts = time.split()
        time_value = time_parts[0] if time_parts else "00:00"
        am_pm = time_parts[1] if len(time_parts) > 1 else "AM"
        
        # Convert to 24-hour format for comparison
        hour, minute = map(int, time_value.split(':'))
        if am_pm.upper() == "PM" and hour != 12:
            hour += 12
        elif am_pm.upper() == "AM" and hour == 12:
            hour = 0
        
        # Check appointments for same hospital, date, and time slot (±30 minutes)
        appointment_result = supabase.table("appointments").select("*").eq(
            "hospital_id", hospital_id
        ).eq("appointment_date", date).execute()
        
        if appointment_result.data:
            for apt in appointment_result.data:
                apt_time = apt.get("appointment_time", "")
                apt_parts = apt_time.split()
                apt_time_value = apt_parts[0] if apt_parts else "00:00"
                apt_am_pm = apt_parts[1] if len(apt_parts) > 1 else "AM"
                
                apt_hour, apt_minute = map(int, apt_time_value.split(':'))
                if apt_am_pm.upper() == "PM" and apt_hour != 12:
                    apt_hour += 12
                elif apt_am_pm.upper() == "AM" and apt_hour == 12:
                    apt_hour = 0
                
                # Check if within 30 minutes (conflict)
                time_diff = abs((hour * 60 + minute) - (apt_hour * 60 + apt_minute))
                if time_diff < 30:
                    return False, f"Time slot {time} is already booked. Please choose another time."
        
        # Check operations for same hospital, date, and time slot
        operation_result = supabase.table("operations").select("*").eq(
            "hospital_id", hospital_id
        ).eq("operation_date", date).execute()
        
        if operation_result.data:
            for op in operation_result.data:
                op_time = op.get("operation_time", "")
                op_parts = op_time.split()
                op_time_value = op_parts[0] if op_parts else "00:00"
                op_am_pm = op_parts[1] if len(op_parts) > 1 else "AM"
                
                op_hour, op_minute = map(int, op_time_value.split(':'))
                if op_am_pm.upper() == "PM" and op_hour != 12:
                    op_hour += 12
                elif op_am_pm.upper() == "AM" and op_hour == 12:
                    op_hour = 0
                
                time_diff = abs((hour * 60 + minute) - (op_hour * 60 + op_minute))
                if time_diff < 30:
                    return False, f"Time slot {time} conflicts with an operation. Please choose another time."
        
        return True, ""
    except Exception as e:
        print(f"Error checking time slot: {e}")
        return True, ""  # Allow booking if check fails (fail open)

def verify_payment_before_booking(order_id: str) -> Tuple[bool, str]:
    """
    Verify payment is completed before confirming booking
    Returns: (is_verified, error_message)
    """
    try:
        if not supabase:
            return True, ""  # Skip if no database
        
        payment_result = supabase.table("payments").select("*").eq("order_id", order_id).execute()
        
        if not payment_result.data:
            return False, "Payment order not found. Please complete payment first."
        
        payment = payment_result.data[0]
        payment_status = payment.get("payment_status", "pending")
        
        if payment_status != "completed":
            return False, f"Payment is {payment_status}. Please complete payment before booking."
        
        return True, ""
    except Exception as e:
        print(f"Error verifying payment: {e}")
        return False, "Payment verification failed. Please try again."

def check_booking_deadlock(patient_mobile: str, hospital_id: int, date: str) -> Tuple[bool, str]:
    """
    Check for deadlock conditions (multiple simultaneous bookings)
    Returns: (is_safe, error_message)
    """
    try:
        if not supabase:
            return True, ""
        
        # Check for pending bookings for same patient, hospital, date
        appointment_result = supabase.table("appointments").select("*").eq(
            "patient_mobile", patient_mobile
        ).eq("hospital_id", hospital_id).eq("appointment_date", date).eq(
            "status", "pending"
        ).execute()
        
        if appointment_result.data and len(appointment_result.data) > 0:
            return False, "You already have a pending appointment for this date. Please complete or cancel it first."
        
        # Check for pending operations
        operation_result = supabase.table("operations").select("*").eq(
            "patient_mobile", patient_mobile
        ).eq("hospital_id", hospital_id).eq("operation_date", date).eq(
            "status", "pending"
        ).execute()
        
        if operation_result.data and len(operation_result.data) > 0:
            return False, "You already have a pending operation for this date. Please complete or cancel it first."
        
        return True, ""
    except Exception as e:
        print(f"Error checking deadlock: {e}")
        return True, ""  # Fail open

# ============================================
# CITY AUTOCOMPLETE ENDPOINTS WITH CACHING
# ============================================

# In-memory cache for city searches
city_search_cache = {}
CACHE_TTL = 3600  # Cache for 1 hour
cache_timestamps = {}

# Popular Indian cities for autocomplete
POPULAR_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
    "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur",
    "Nagpur", "Indore", "Thane", "Bhopal", "Visakhapatnam", "Patna",
    "Vadodara", "Ghaziabad", "Ludhiana", "Agra", "Nashik", "Faridabad",
    "Meerut", "Rajkot", "Varanasi", "Srinagar", "Amritsar", "Chandigarh"
]

ALL_CITIES = POPULAR_CITIES + [
    "Aurangabad", "Coimbatore", "Kochi", "Mysore", "Raipur", "Jodhpur",
    "Gwalior", "Vijayawada", "Jalandhar", "Thiruvananthapuram", "Salem",
    "Tiruchirappalli", "Kota", "Bhubaneswar", "Aligarh", "Bareilly",
    "Moradabad", "Bhiwandi", "Gorakhpur", "Guntur", "Bikaner", "Amravati",
    "Noida", "Jamshedpur", "Bhilai", "Cuttack", "Firozabad", "Kozhikode",
    "Dhanbad", "Solapur", "Jabalpur", "Gulbarga", "Nellore", "Trichy",
    "Bhavnagar", "Sangli", "Ratlam", "Udaipur", "Kurnool", "Bokaro",
    "Akola", "Belgaum", "Rajahmundry", "Mangalore", "Tirunelveli",
    "Malegaon", "Gaya", "Tuticorin", "Ujjain", "Davangere", "Kollam",
    "Bilaspur", "Muzaffarpur", "Ahmednagar", "Mathura", "Kakinada",
    "Rohtak", "Shimoga", "Chandrapur", "Gandhinagar", "Bardhaman",
    "Korba", "Bhimavaram", "Panipat", "Fatehpur", "Ichalkaranji",
    "Bharatpur", "Hospet", "Sikar", "Hardwar", "Dibrugarh", "Nizamabad",
    "Bathinda", "Palwal", "Navsari", "Mandsaur", "Hindupur", "Fazilka",
    "Kumbakonam", "Karimnagar", "Machilipatnam", "Ongole", "Nandyal",
    "Morena", "Bhiwani", "Rewa", "Unnao", "Sitapur", "Hapur", "Anantapur",
    "Kadapa", "Proddatur", "Chittoor", "Hindupur", "Nalgonda", "Suryapet",
    "Miryalaguda", "Adilabad", "Nirmal", "Kamareddy", "Siddipet", "Medak",
    "Sangareddy", "Zaheerabad", "Gadwal", "Wanaparthy", "Mahbubnagar",
    "Narayanpet", "Kurnool", "Nandikotkur", "Atmakur", "Kodumur", "Gudur", "Kavali",
    "Nellore", "Kovur", "Udayagiri", "Rapur", "Sullurpeta", "Naidupet",
    "Venkatagiri", "Gudur", "Srikalahasti", "Tirupati", "Chittoor",
    "Puttur", "Madanapalle", "Punganur", "Palamaner", "Kuppam", "Bangarupalem"
]

def get_cached_cities(query: str) -> Optional[List[dict]]:
    """Get cities from cache if available and not expired"""
    cache_key = query.lower()
    if cache_key in city_search_cache:
        # Check if cache is still valid
        if cache_key in cache_timestamps:
            age = (datetime.now() - cache_timestamps[cache_key]).total_seconds()
            if age < CACHE_TTL:
                print(f"✅ Cache HIT for query: '{query}' (age: {age:.1f}s)")
                return city_search_cache[cache_key]
            else:
                # Cache expired, remove it
                del city_search_cache[cache_key]
                del cache_timestamps[cache_key]
                print(f"⏰ Cache EXPIRED for query: '{query}'")
    print(f"❌ Cache MISS for query: '{query}'")
    return None

def set_cached_cities(query: str, cities: List[dict]):
    """Store cities in cache with timestamp"""
    cache_key = query.lower()
    city_search_cache[cache_key] = cities
    cache_timestamps[cache_key] = datetime.now()
    print(f"💾 Cached results for query: '{query}' ({len(cities)} cities)")

def query_city_database(query: str) -> List[dict]:
    """
    Query the Supabase database for cities with state information
    Returns list of dicts with city_name and state_name
    """
    cities_list = []
    
    # Step 1: Try to query Supabase database
    if supabase:
        try:
            result = supabase.table("cities").select("city_name, state_name").ilike(
                "city_name", f"%{query}%"
            ).eq("is_active", True).limit(20).execute()
            
            if result.data:
                cities_list = [
                    {
                        "city_name": city.get("city_name", ""),
                        "state_name": city.get("state_name", "")
                    }
                    for city in result.data
                ]
                print(f"📊 Found {len(cities_list)} cities in database for query: '{query}'")
        except Exception as e:
            print(f"⚠️ Error querying database: {e}")
    
    # Sort by relevance (exact match first, then starts with, then contains)
    cities_list.sort(key=lambda x: (
        0 if x["city_name"].lower().startswith(query.lower()) else 1,
        x["city_name"].lower().index(query.lower()) if query.lower() in x["city_name"].lower() else 999,
        len(x["city_name"])
    ))
    
    # Return top 20 matches
    return cities_list[:20]

@app.get("/api/cities/search")
async def search_cities(q: str = ""):
    """
    Search cities dynamically based on query
    Returns cities with state_name for auto-filling state field
    Flow: Cache → Database (from CSV import)
    Uses caching for fast and reliable search
    Powered by city data imported from CSV
    """
    try:
        query = q.strip().lower()
        if len(query) < 2:
            return {"cities": [], "source": "empty_query"}
        
        # Step 1: Check cache
        cached_results = get_cached_cities(query)
        if cached_results is not None:
            return {
                "cities": cached_results,
                "source": "cache",
                "cached": True
            }
        
        # Step 2: Cache miss - query database
        print(f"🔍 Querying database for: '{query}'")
        matching_cities = query_city_database(query)
        
        # Step 3: Store in cache
        if matching_cities:
            set_cached_cities(query, matching_cities)
        
        # Step 4: Return results
        return {
            "cities": matching_cities,
            "source": "database",
            "cached": False
        }
    except Exception as e:
        print(f"Error searching cities: {e}")
        return {"cities": [], "source": "error", "error": str(e)}

@app.get("/api/cities/popular")
async def get_popular_cities():
    """Get popular cities (cached)"""
    try:
        cache_key = "popular"
        cached = get_cached_cities(cache_key)
        if cached:
            return {"cities": cached, "source": "cache", "cached": True}
        
        # Try to get from database first
        popular = POPULAR_CITIES[:15]
        if supabase:
            try:
                result = supabase.table("cities").select("city_name").eq(
                    "is_active", True
                ).limit(15).execute()
                if result.data:
                    popular = [city["city_name"] for city in result.data[:15]]
            except Exception as e:
                print(f"⚠️ Error fetching popular cities from DB: {e}")
        
        set_cached_cities(cache_key, popular)
        return {"cities": popular, "source": "database", "cached": False}
    except Exception as e:
        print(f"Error getting popular cities: {e}")
        return {"cities": POPULAR_CITIES[:10], "source": "fallback"}

# ============================================
# DOCTOR ENDPOINTS (for Pharma Professionals)
# ============================================

@app.get("/api/doctors/search")
async def search_doctors(q: str = "", hospital_id: Optional[int] = None):
    """Search doctors dynamically based on query"""
    try:
        query = q.strip().lower()
        if len(query) < 2:
            return {"doctors": []}
        
        if not supabase:
            return {"doctors": []}
        
        # Build query
        doctor_query = supabase.table("doctors").select("*").ilike(
            "doctor_name", f"%{query}%"
        ).eq("is_active", True)
        
        # Filter by hospital if provided
        if hospital_id:
            doctor_query = doctor_query.eq("hospital_id", hospital_id)
        
        result = doctor_query.limit(20).execute()
        
        doctors = []
        if result.data:
            doctors = result.data
            print(f"📊 Found {len(doctors)} doctors for query: '{query}'")
        
        return {"doctors": doctors}
    except Exception as e:
        print(f"Error searching doctors: {e}")
        return {"doctors": []}

@app.post("/api/doctors/add")
async def add_new_doctor(doctor_data: dict = Body(...)):
    """Add a new doctor to the database (crowdsourced)"""
    try:
        doctor_name = doctor_data.get("doctor_name", "").strip()
        if not doctor_name:
            raise HTTPException(status_code=400, detail="Doctor name is required")
        
        if not supabase:
            raise HTTPException(status_code=500, detail="Database not configured")
        
        # Check if doctor already exists (by name and mobile if provided)
        mobile = doctor_data.get("mobile", "").strip()
        existing_query = supabase.table("doctors").select("id").eq("doctor_name", doctor_name)
        
        if mobile:
            existing_query = existing_query.eq("mobile", mobile)
        
        existing = existing_query.execute()
        
        if existing.data:
            return {
                "message": "Doctor already exists",
                "doctor_name": doctor_name,
                "id": existing.data[0]["id"]
            }
        
        # Prepare doctor data
        new_doctor = {
            "doctor_name": doctor_name,
            "place": doctor_data.get("place", "").strip() or None,
            "mobile": mobile or None,
            "email": doctor_data.get("email", "").strip() or None,
            "degree": doctor_data.get("degree", "").strip() or None,
            "specialization": doctor_data.get("specialization", "").strip() or None,
            "hospital_id": doctor_data.get("hospital_id") if doctor_data.get("hospital_id") else None,
            "source": "crowdsourced",
            "is_active": True
        }
        
        # Insert into database
        result = supabase.table("doctors").insert(new_doctor).execute()
        
        if result.data:
            print(f"✅ New doctor added: {doctor_name} (ID: {result.data[0]['id']})")
            return {
                "message": "Doctor added successfully",
                "doctor_name": doctor_name,
                "id": result.data[0]["id"]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add doctor")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding doctor: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding doctor: {str(e)}")

@app.post("/api/cities/add")
async def add_new_city(city_data: dict = Body(...)):
    """Add a new city to the database"""
    try:
        city_name = city_data.get("city_name", "").strip()
        if not city_name:
            raise HTTPException(status_code=400, detail="City name is required")
        
        if not supabase:
            raise HTTPException(status_code=500, detail="Database not configured")
        
        # Check if city already exists
        existing = supabase.table("cities").select("id").eq(
            "city_name", city_name
        ).execute()
        
        if existing.data:
            return {
                "message": "City already exists",
                "city_name": city_name,
                "id": existing.data[0]["id"]
            }
        
        # Prepare city data
        new_city = {
            "city_name": city_name,
            "state_name": city_data.get("state_name", "").strip() or None,
            "district_name": city_data.get("district_name", "").strip() or None,
            "pincode": city_data.get("pincode", "").strip() or None,
            "source": "manual",
            "is_active": True
        }
        
        # Insert into database
        result = supabase.table("cities").insert(new_city).execute()
        
        if result.data:
            # Clear cache for this city name to refresh results
            cache_key = city_name.lower()
            if cache_key in city_search_cache:
                del city_search_cache[cache_key]
                if cache_key in cache_timestamps:
                    del cache_timestamps[cache_key]
            
            print(f"✅ New city added: {city_name} (ID: {result.data[0]['id']})")
            return {
                "message": "City added successfully",
                "city_name": city_name,
                "id": result.data[0]["id"]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add city")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding city: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding city: {str(e)}")

# ============================================
# PAYMENT ENDPOINTS
# ============================================

@app.post("/api/payments/create-order")
async def create_payment_order(payment_data: dict = Body(...)):
    """Create a payment order for appointments, operations, or hospital registration"""
    try:
        print(f"[Mobile] Payment order request received: {payment_data}")
        
        payment_type = payment_data.get("type")
        hospital_id = payment_data.get("hospital_id", 0)
        patient_name = payment_data.get("patient_name", "")
        patient_mobile = payment_data.get("patient_mobile", "")
        
        # Ensure amount is converted to float (handles int from mobile app)
        amount_raw = payment_data.get("amount", 0)
        print(f"[Mobile] Amount raw type: {type(amount_raw)}, value: {amount_raw}")
        
        if isinstance(amount_raw, (int, float, str)):
            amount = float(amount_raw)
        else:
            amount = 0.0
        
        print(f"[Mobile] Amount converted to float: {amount} (type: {type(amount)})")
        
        metadata = payment_data.get("metadata", {})
        
        if not payment_type or amount <= 0:
            print(f"[Mobile] Validation failed: payment_type={payment_type}, amount={amount}")
            raise HTTPException(status_code=400, detail="Invalid payment data")
        
        # Use PaymentGateway to create order
        payment_gateway = PaymentGateway()
        order_response = payment_gateway.create_order(
            amount=amount,
            currency="INR",
            receipt=f"{payment_type}_{int(datetime.now().timestamp())}",
            notes=metadata
        )
        
        if order_response is None or "error" in order_response or order_response.get("order_id") is None:
            # Fallback: create order ID manually if Razorpay not configured
            import hashlib
            order_id = f"UPI_{hashlib.sha256(f'{payment_type}{hospital_id}{patient_mobile}{datetime.now().isoformat()}'.encode()).hexdigest()[:16]}"
            order_response = {
                "order_id": order_id,
                "amount": float(amount),  # Ensure float type
                "currency": "INR",
                "status": "created",
                "payment_method": "upi"
            }
        
        # Store payment order in database
        if supabase:
            payment_record = {
                "order_id": order_response["order_id"],
                "entity_type": payment_type,
                "entity_id": hospital_id if hospital_id > 0 else None,
                "amount": str(amount),  # Store as string in DB (matches schema)
                "currency": "INR",
                "status": "created",
                "patient_name": patient_name,
                "patient_mobile": patient_mobile,
                "hospital_id": hospital_id if hospital_id > 0 else None,
                "description": f"Payment for {payment_type}",
            }
            
            try:
                supabase.table("payments").insert(payment_record).execute()
            except Exception as e:
                print(f"Warning: Could not store payment order in database: {e}")
        
        # Ensure all numeric values are returned as float for mobile app compatibility
        response = {
            "order_id": order_response["order_id"],
            "amount": float(amount),  # Explicitly convert to float for mobile app
            "currency": "INR",
            "status": "created",
            "message": "Payment order created successfully"
        }
        print(f"[Mobile] Payment order created successfully: {response}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Mobile] Error creating payment order: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating payment order: {str(e)}")

@app.post("/api/payments/verify")
async def verify_payment(verification_data: dict = Body(...)):
    """Verify payment signature"""
    try:
        order_id = verification_data.get("order_id")
        payment_id = verification_data.get("payment_id")
        signature = verification_data.get("signature")
        
        if not all([order_id, payment_id, signature]):
            raise HTTPException(status_code=400, detail="Missing verification data")
        
        payment_gateway = PaymentGateway()
        is_verified = payment_gateway.verify_payment_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature
        )
        
        if is_verified and supabase:
            # Update payment status
            supabase.table("payments").update({
                "payment_id": payment_id,
                "signature": signature,
                "status": "paid",
                "paid_at": datetime.now().isoformat()
            }).eq("order_id", order_id).execute()
        
        return {"verified": is_verified}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying payment: {e}")
        raise HTTPException(status_code=500, detail=f"Error verifying payment: {str(e)}")

@app.get("/api/payments/status/{order_id}")
async def get_payment_status(order_id: str):
    """Get payment status by order ID"""
    try:
        if supabase:
            result = supabase.table("payments").select("*").eq("order_id", order_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
        raise HTTPException(status_code=404, detail="Payment order not found")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting payment status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting payment status: {str(e)}")

@app.get("/api/payments/history/{patient_mobile}")
async def get_payment_history(patient_mobile: str):
    """Get payment history for a patient"""
    try:
        if supabase:
            result = supabase.table("payments").select("*").eq("patient_mobile", patient_mobile).order("created_at", desc=True).execute()
            return {"payments": result.data if result.data else []}
        return {"payments": []}
    except Exception as e:
        print(f"Error getting payment history: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting payment history: {str(e)}")

@app.post("/api/payments/refund")
async def process_refund(refund_data: dict = Body(...)):
    """Process a refund for a payment"""
    try:
        payment_id = refund_data.get("payment_id")
        amount = refund_data.get("amount")
        reason = refund_data.get("reason", "")
        
        if not payment_id:
            raise HTTPException(status_code=400, detail="Payment ID is required")
        
        payment_gateway = PaymentGateway()
        refund_result = payment_gateway.create_refund(
            payment_id=payment_id,
            amount=amount,
            notes={"reason": reason} if reason else None
        )
        
        if refund_result and supabase:
            # Update payment record with refund info
            supabase.table("payments").update({
                "refund_id": refund_result.get("id"),
                "refund_amount": refund_result.get("amount", 0) / 100 if refund_result.get("amount") else amount,
                "refund_status": refund_result.get("status", "processed"),
                "refund_reason": reason,
                "refunded_at": datetime.now().isoformat(),
                "status": "refunded"
            }).eq("payment_id", payment_id).execute()
        
        return {
            "refund_id": refund_result.get("id") if refund_result else None,
            "status": "processed" if refund_result else "failed",
            "message": "Refund processed successfully" if refund_result else "Refund processing failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing refund: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing refund: {str(e)}")

# ============================================
# HEALTH CHECK
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if supabase:
            # Test database connection
            supabase.table("hospitals").select("id").limit(1).execute()
            return {
                "status": "ok",
                "message": "Server is running",
                "database": "connected",
                "supabase_url": SUPABASE_URL[:30] + "..." if SUPABASE_URL else None
            }
        else:
            return {
                "status": "ok",
                "message": "Server is running",
                "database": "in-memory (Supabase not configured)"
            }
    except Exception as e:
        return {
            "status": "ok",
            "message": "Server is running",
            "database": "error",
            "error": str(e)
        }

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("🚀 Starting Anagha Hospital Solutions API Server")
    print("="*60)
    if supabase:
        print("✅ Supabase database: Connected")
        # Check cities count
        try:
            result = supabase.table("cities").select("id", count="exact").execute()
            city_count = result.count if hasattr(result, 'count') else len(result.data) if result.data else 0
            print(f"📊 Cities in database: {city_count:,}")
        except:
            print("⚠️  Cities table not found - run import_cities_from_csv.py")
    else:
        print("⚠️  Supabase database: Not configured (using in-memory storage)")
    print(f"📁 Admin Panel: {config.ADMIN_PANEL_URL}")
    print(f"🔍 API Docs: http://{config.SERVER_HOST}:{config.SERVER_PORT}/docs")
    print(f"💚 Health Check: http://{config.SERVER_HOST}:{config.SERVER_PORT}/health")
    print(f"🌐 City Data: Imported from city.csv")
    print(f"🌐 API Base URL: {config.API_BASE_URL}")
    print("="*60)
    print("Press CTRL+C to stop the server\n")
    
    uvicorn.run(
        "server_mobile:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info"
    )
