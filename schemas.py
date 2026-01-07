from pydantic import BaseModel, EmailStr, field_validator, model_validator, validator
from datetime import date, datetime
from typing import Optional
from models import UserRole, AppointmentStatus, OperationStatus, Specialty, HospitalStatus

# User Schemas
class UserBase(BaseModel):
    name: str
    mobile: str
    role: UserRole
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    hospital_id: Optional[int] = None  # Required for patient and pharma, optional for doctor
    email: Optional[str] = None  # Optional email field
    address: Optional[str] = None  # Frontend may send single address field

class UserCreate(UserBase):
    password: str
    
    # Pharma Professional fields
    company_name: Optional[str] = None
    product1: Optional[str] = None
    product2: Optional[str] = None
    product3: Optional[str] = None
    product4: Optional[str] = None
    
    # Doctor fields
    degree: Optional[str] = None
    institute_name: Optional[str] = None
    experience1: Optional[str] = None
    experience2: Optional[str] = None
    experience3: Optional[str] = None
    experience4: Optional[str] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v
    
    @model_validator(mode='after')
    def validate_role_fields(self):
        # Convert role to enum if it's a string
        role_value = self.role.value if hasattr(self.role, 'value') else str(self.role)
        
        if role_value == "pharma" or self.role == UserRole.PHARMA:
            if not self.company_name:
                raise ValueError('Company name is required for pharma professionals')
            if not self.hospital_id:
                raise ValueError('Hospital selection is required for pharma professionals')
        elif role_value == "patient" or self.role == UserRole.PATIENT:
            # Hospital is optional for patients (frontend allows it to be optional)
            pass
        elif role_value == "doctor" or self.role == UserRole.DOCTOR:
            if not self.degree:
                raise ValueError('Degree is required for doctors')
            if not self.institute_name:
                raise ValueError('Institute name is required for doctors')
        return self

class UserLogin(BaseModel):
    mobile: str
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Appointment Schemas
class AppointmentBase(BaseModel):
    doctor_id: int
    date: date
    time_slot: str
    
    @validator('time_slot')
    def validate_time_slot(cls, v):
        # Morning slots: 9:30 AM to 3:30 PM
        # Evening slots: 6:00 PM to 8:30 PM
        valid_slots = [
            "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
            "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"
        ]
        if v not in valid_slots:
            raise ValueError(f'Invalid time slot. Must be one of: {", ".join(valid_slots)}')
        return v

class AppointmentCreate(AppointmentBase):
    reason: Optional[str] = None  # Allow reason/notes for appointments

class AppointmentResponse(AppointmentBase):
    id: int
    user_id: int
    hospital_id: int  # Mandatory hospital_id (now consistently included)
    status: AppointmentStatus
    created_at: datetime
    user_name: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None  # Aligned with operations
    
    class Config:
        from_attributes = True

# Operation Schemas
class OperationBase(BaseModel):
    specialty: Specialty
    date: date
    doctor_id: int
    notes: Optional[str] = None

class OperationCreate(OperationBase):
    pass

class OperationResponse(OperationBase):
    id: int
    patient_id: int
    hospital_id: int  # Mandatory hospital_id (aligned with appointments)
    status: OperationStatus
    created_at: datetime
    patient_name: Optional[str] = None
    doctor_name: Optional[str] = None
    hospital_name: Optional[str] = None  # Aligned with appointments
    
    class Config:
        from_attributes = True

# Token Schema
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Hospital Schemas
class HospitalBase(BaseModel):
    name: str
    email: EmailStr
    mobile: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_line3: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    # UPI IDs for different payment apps
    upi_id: Optional[str] = None  # Default/Universal UPI ID
    gpay_upi_id: Optional[str] = None  # Google Pay UPI ID
    phonepay_upi_id: Optional[str] = None  # PhonePe UPI ID
    paytm_upi_id: Optional[str] = None  # Paytm UPI ID
    bhim_upi_id: Optional[str] = None  # BHIM UPI ID

class HospitalCreate(HospitalBase):
    payment_id: Optional[int] = None  # Payment ID for registration fee
    plan_name: Optional[str] = None  # Selected package/plan name

class HospitalResponse(HospitalBase):
    id: int
    status: HospitalStatus
    registration_date: datetime
    approved_date: Optional[datetime] = None
    
    class Config:
        from_attributes = True

