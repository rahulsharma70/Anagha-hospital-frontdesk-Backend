"""
Model enums for type hints and validation
Note: Since we're using Supabase, these are just enums for schemas.
The actual database schema is managed by Supabase.
"""
import enum

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    PHARMA = "pharma"
    DOCTOR = "doctor"

class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    VISITED = "visited"

class OperationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class Specialty(str, enum.Enum):
    ORTHO = "ortho"
    GYN = "gyn"
    SURGERY = "surgery"

# Note: SQLAlchemy model classes removed - using Supabase now
# These enums are still used by schemas.py for validation

class HospitalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# Note: SQLAlchemy model classes removed - using Supabase now

class PaymentStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"

class PaymentMethod(str, enum.Enum):
    UPI_GPAY = "gpay"
    UPI_PHONEPE = "phonepay"
    UPI_PAYTM = "paytm"
    UPI_BHIM = "bhimupi"

# Note: SQLAlchemy model classes removed - using Supabase now

