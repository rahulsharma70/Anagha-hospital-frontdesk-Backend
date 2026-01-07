from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from database import get_supabase
# Note: Hospital SQLAlchemy model removed - using Supabase now
from schemas import HospitalCreate
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import logging
from services.whatsapp_service import open_whatsapp_session, get_whatsapp_driver, check_whatsapp_session_health, close_whatsapp_session
from services.email_service import send_hospital_registration_email
from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])

@router.post("/register", response_model=dict)
def register_hospital(
    hospital: HospitalCreate,
    background_tasks: BackgroundTasks
):
    """Register a new hospital (requires payment and admin approval) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Validate payment is provided
        if not hospital.payment_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment is required for hospital registration. Please complete payment first."
            )
        
        # Verify payment exists and is completed
        payment_result = supabase.table("payments").select("*").eq("id", hospital.payment_id).execute()
        if not payment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment = payment_result.data[0]
        
        # Check payment status
        if payment.get("status") != "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Payment not completed. Current status: {payment.get('status')}. Please complete payment first."
            )
        
        # Verify payment is for hospital registration
        payment_metadata = payment.get("metadata")
        if not payment_metadata or payment_metadata.get("type") != "hospital_registration":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment. This payment is not for hospital registration."
            )
        
        # Check if payment has already been used
        if payment.get("hospital_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This payment has already been used for a hospital registration."
            )
        
        # Check if email already exists
        existing = supabase.table("hospitals").select("id").eq("email", hospital.email).execute()
        if existing.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hospital with this email already registered"
            )
        
        # Prepare hospital record for Supabase
        # Only include fields that have values (Supabase doesn't like None for some columns)
        # Note: If database schema is missing columns, they will be skipped
        hospital_record = {
            "name": hospital.name,
            "email": hospital.email,
            "mobile": hospital.mobile,
            "status": "pending",
        }
        
        # Add optional fields only if they have values
        # Address fields
        if hospital.address_line1:
            hospital_record["address_line1"] = hospital.address_line1
        if hospital.address_line2:
            hospital_record["address_line2"] = hospital.address_line2
        if hospital.address_line3:
            hospital_record["address_line3"] = hospital.address_line3
        
        # Location fields - only add if they have values
        # Note: If these columns don't exist in database, the insert will fail with a clear error
        if hospital.city:
            hospital_record["city"] = hospital.city
        if hospital.state:
            hospital_record["state"] = hospital.state
        if hospital.pincode:
            hospital_record["pincode"] = hospital.pincode
        
        # UPI fields
        if hospital.upi_id:
            hospital_record["upi_id"] = hospital.upi_id
        if hospital.gpay_upi_id:
            hospital_record["gpay_upi_id"] = hospital.gpay_upi_id
        if hospital.phonepay_upi_id:
            hospital_record["phonepay_upi_id"] = hospital.phonepay_upi_id
        if hospital.paytm_upi_id:
            hospital_record["paytm_upi_id"] = hospital.paytm_upi_id
        if hospital.bhim_upi_id:
            hospital_record["bhim_upi_id"] = hospital.bhim_upi_id
        
                # Insert into Supabase
        try:
            result = supabase.table("hospitals").insert(hospital_record).execute()

        except Exception as insert_error:
            error_str = str(insert_error).lower()

            # Handle missing column errors gracefully
            if "column" in error_str and (
                "not found" in error_str or "does not exist" in error_str
            ):
                # Retry without location fields if they caused the error
                if any(col in error_str for col in ["city", "state", "pincode"]):
                    hospital_record.pop("city", None)
                    hospital_record.pop("state", None)
                    hospital_record.pop("pincode", None)

                    result = supabase.table("hospitals").insert(hospital_record).execute()
                else:
                    raise
            else:
                raise

        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register hospital"
            )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if it's a column not found error
        if "column" in error_msg.lower() and "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database schema mismatch: {error_msg}. Please ensure the database schema is up to date."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering hospital: {error_msg}"
        )

@router.get("/payment-info")
def get_hospital_payment_info(hospital_id: Optional[int] = None):
    """Get hospital payment UPI IDs for homepage (public endpoint) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        # Return default values if database not configured
        return {
            "upi_id": "hospital@upi",
            "gpay_upi_id": "hospital@upi",
            "phonepay_upi_id": "hospital@upi",
            "paytm_upi_id": "hospital@upi",
            "bhim_upi_id": "hospital@upi"
        }
    
    try:
        if hospital_id:
            result = supabase.table("hospitals").select("*").eq("id", hospital_id).eq("status", "approved").execute()
        else:
            # Get first approved hospital as default
            result = supabase.table("hospitals").select("*").eq("status", "approved").limit(1).execute()
        
        if not result.data:
            # Return default values if no hospital found
            return {
                "upi_id": "hospital@upi",
                "gpay_upi_id": "hospital@upi",
                "phonepay_upi_id": "hospital@upi",
                "paytm_upi_id": "hospital@upi",
                "bhim_upi_id": "hospital@upi"
            }
        
        hospital = result.data[0]
        default_upi = hospital.get("upi_id") or "hospital@upi"
        return {
            "upi_id": default_upi,
            "gpay_upi_id": hospital.get("gpay_upi_id") or default_upi,
            "phonepay_upi_id": hospital.get("phonepay_upi_id") or default_upi,
            "paytm_upi_id": hospital.get("paytm_upi_id") or default_upi,
            "bhim_upi_id": hospital.get("bhim_upi_id") or default_upi
        }
    except Exception as e:
        print(f"Error fetching hospital payment info: {e}")
        # Return default values on error
        return {
            "upi_id": "hospital@upi",
            "gpay_upi_id": "hospital@upi",
            "phonepay_upi_id": "hospital@upi",
            "paytm_upi_id": "hospital@upi",
            "bhim_upi_id": "hospital@upi"
        }

@router.get("/", response_model=List[dict])
def get_hospitals(
    status_filter: Optional[str] = None
):
    """Get list of hospitals (filtered by status if provided) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        query = supabase.table("hospitals").select("*")
        if status_filter:
            query = query.eq("status", status_filter)
        result = query.order("created_at", desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error fetching hospitals: {e}")
        return []

@router.get("/approved", response_model=List[dict])
def get_approved_hospitals():
    """Get list of approved hospitals - using Supabase. Returns all hospitals (approved and pending) for booking purposes."""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        # Return all hospitals (approved and pending) for booking purposes
        # This allows users to book with hospitals that are pending approval
        result = supabase.table("hospitals").select("*").order("name").execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error fetching hospitals: {e}")
        return []

@router.get("/{hospital_id}", response_model=dict)
def get_hospital_by_id(
    hospital_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get hospital by ID - using Supabase. Requires authentication."""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching hospital: {str(e)}"
        )

@router.put("/{hospital_id}/approve")
def approve_hospital(hospital_id: int):
    """Approve a hospital registration (admin function) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if hospital exists
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        # Update status to approved
        update_result = supabase.table("hospitals").update({
            "status": "approved",
            "approved_date": datetime.utcnow().isoformat()
        }).eq("id", hospital_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to approve hospital"
            )
        
        return {"message": "Hospital approved successfully", "hospital": update_result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error approving hospital: {str(e)}"
        )

@router.put("/{hospital_id}/reject")
def reject_hospital(hospital_id: int):
    """Reject a hospital registration (admin function) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if hospital exists
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        # Update status to rejected
        update_result = supabase.table("hospitals").update({
            "status": "rejected"
        }).eq("id", hospital_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reject hospital"
            )
        
        return {"message": "Hospital rejected successfully", "hospital": update_result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rejecting hospital: {str(e)}"
        )


# WhatsApp Admin Endpoints

class WhatsAppSettingsUpdate(BaseModel):
    whatsapp_enabled: Optional[str] = None
    whatsapp_confirmation_template: Optional[str] = None
    whatsapp_followup_template: Optional[str] = None


class SMTPConfigUpdate(BaseModel):
    """Pydantic model for updating SMTP configuration"""
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_enabled: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None
    whatsapp_reminder_template: Optional[str] = None


@router.put("/{hospital_id}/whatsapp-settings")
def update_whatsapp_settings(
    hospital_id: int,
    settings: WhatsAppSettingsUpdate
):
    """Update WhatsApp settings for a hospital (admin function) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if hospital exists
        hospital_result = supabase.table("hospitals").select("id").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        # Prepare update data
        update_data = {}
        if settings.whatsapp_enabled is not None:
            update_data["whatsapp_enabled"] = settings.whatsapp_enabled
        if settings.whatsapp_confirmation_template is not None:
            update_data["whatsapp_confirmation_template"] = settings.whatsapp_confirmation_template
        if settings.whatsapp_followup_template is not None:
            update_data["whatsapp_followup_template"] = settings.whatsapp_followup_template
        if settings.whatsapp_reminder_template is not None:
            update_data["whatsapp_reminder_template"] = settings.whatsapp_reminder_template
        
        # Update hospital
        result = supabase.table("hospitals").update(update_data).eq("id", hospital_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update WhatsApp settings"
            )
        
        hospital = result.data[0]
        return {
            "message": "WhatsApp settings updated",
            "whatsapp_enabled": hospital.get("whatsapp_enabled"),
            "whatsapp_confirmation_template": hospital.get("whatsapp_confirmation_template"),
            "whatsapp_followup_template": hospital.get("whatsapp_followup_template"),
            "whatsapp_reminder_template": hospital.get("whatsapp_reminder_template")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating WhatsApp settings: {str(e)}"
        )


@router.get("/{hospital_id}/whatsapp-status")
def get_whatsapp_status(hospital_id: int):
    """Check WhatsApp session status for a hospital - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        hospital_result = supabase.table("hospitals").select("whatsapp_enabled").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        hospital = hospital_result.data[0]
        is_healthy = check_whatsapp_session_health(hospital_id)
        
        return {
            "hospital_id": hospital_id,
            "whatsapp_enabled": hospital.get("whatsapp_enabled") == "true" or hospital.get("whatsapp_enabled") is True,
            "session_active": is_healthy,
            "message": "Session active" if is_healthy else "Session expired or not initialized"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking WhatsApp status: {str(e)}"
        )


@router.post("/{hospital_id}/whatsapp-init")
def initialize_whatsapp_session(hospital_id: int):
    """Initialize WhatsApp Web session for a hospital (opens browser for QR scan) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        hospital_result = supabase.table("hospitals").select("whatsapp_enabled").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        hospital = hospital_result.data[0]
        # Enable WhatsApp if not already enabled
        if hospital.get("whatsapp_enabled") != "true" and hospital.get("whatsapp_enabled") is not True:
            supabase.table("hospitals").update({"whatsapp_enabled": "true"}).eq("id", hospital_id).execute()
        
        # Initialize driver (will open browser for QR scan)
        # Hospital admin scans QR once only. Session remains logged in.
        driver = open_whatsapp_session(hospital_id)
        
        if driver:
            return {
                "message": "WhatsApp session initialization started. Please scan QR code in the browser window.",
                "status": "initializing"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize WhatsApp session"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error initializing WhatsApp session: {str(e)}"
        )


@router.post("/{hospital_id}/whatsapp-close")
def close_whatsapp_session_endpoint(hospital_id: int):
    """Close WhatsApp session for a hospital - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        hospital_result = supabase.table("hospitals").select("id").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        
        close_whatsapp_session(hospital_id)
        
        return {
            "message": "WhatsApp session closed successfully",
            "hospital_id": hospital_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error closing WhatsApp session: {str(e)}"
        )


# SMTP Configuration Endpoints

@router.put("/{hospital_id}/smtp-settings")
async def update_smtp_settings(
    hospital_id: int,
    smtp_config: SMTPConfigUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update SMTP settings for a hospital.
    Only hospital admins or system admins can update.
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Verify hospital exists
    hospital_result = supabase.table("hospitals").select("id").eq("id", hospital_id).execute()
    if not hospital_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    
    # Check permissions (system admin/doctor or hospital admin)
    # Allow if user is doctor (system admin) or if user belongs to this hospital
    user_hospital_id = current_user.get("hospital_id")
    if current_user.get("role") != "doctor" and user_hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Only system admins or hospital admins can update SMTP settings"
        )
    
    # Prepare update data
    update_data = {}
    if smtp_config.smtp_host is not None:
        update_data["smtp_host"] = smtp_config.smtp_host
    if smtp_config.smtp_port is not None:
        if smtp_config.smtp_port not in [25, 465, 587, 993, 995]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SMTP port. Common ports: 587 (TLS), 465 (SSL), 25 (unsecured)"
            )
        update_data["smtp_port"] = smtp_config.smtp_port
    if smtp_config.smtp_username is not None:
        update_data["smtp_username"] = smtp_config.smtp_username
    if smtp_config.smtp_password is not None:
        update_data["smtp_password"] = smtp_config.smtp_password  # TODO: Encrypt in production
    if smtp_config.smtp_from_email is not None:
        update_data["smtp_from_email"] = smtp_config.smtp_from_email
    if smtp_config.smtp_enabled is not None:
        update_data["smtp_enabled"] = smtp_config.smtp_enabled
    if smtp_config.smtp_use_ssl is not None:
        update_data["smtp_use_ssl"] = smtp_config.smtp_use_ssl
    
    # Update hospital SMTP settings
    result = supabase.table("hospitals").update(update_data).eq("id", hospital_id).execute()
    
    if result.data:
        # Log audit event
        from services.audit_logger import log_audit_event
        log_audit_event(
            event_type="hospital_update",
            user_id=current_user["id"],
            user_role=current_user["role"],
            action="SMTP settings updated",
            resource_type="hospital",
            resource_id=hospital_id,
            details={"updated_fields": list(update_data.keys())},
            ip_address=None  # Can add request.client.host if needed
        )
        
        return {
            "message": "SMTP settings updated successfully",
            "hospital_id": hospital_id,
            "smtp_enabled": result.data[0].get("smtp_enabled", False)
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update SMTP settings"
        )


@router.get("/{hospital_id}/smtp-settings")
async def get_smtp_settings(
    hospital_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get SMTP settings for a hospital (password hidden for security)
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Check permissions
    user_hospital_id = current_user.get("hospital_id")
    if current_user.get("role") != "doctor" and user_hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )
    
    result = supabase.table("hospitals").select(
        "id, smtp_host, smtp_port, smtp_username, smtp_from_email, "
        "smtp_enabled, smtp_use_ssl"
    ).eq("id", hospital_id).execute()
    
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    
    hospital = result.data[0]
    
    # Also check if password is set (without returning it)
    password_check = supabase.table("hospitals").select("smtp_password").eq("id", hospital_id).execute()
    password_set = bool(password_check.data and password_check.data[0].get("smtp_password"))
    
    return {
        "hospital_id": hospital["id"],
        "smtp_host": hospital.get("smtp_host"),
        "smtp_port": hospital.get("smtp_port"),
        "smtp_username": hospital.get("smtp_username"),
        "smtp_from_email": hospital.get("smtp_from_email"),
        "smtp_enabled": hospital.get("smtp_enabled", False),
        "smtp_use_ssl": hospital.get("smtp_use_ssl", False),
        "password_set": password_set  # Indicates if password is configured (without exposing it)
    }


@router.post("/{hospital_id}/test-smtp")
async def test_smtp_connection(
    hospital_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Test SMTP connection with hospital's settings.
    Sends a test email to the hospital's registered email address.
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Check permissions
    user_hospital_id = current_user.get("hospital_id")
    if current_user.get("role") != "doctor" and user_hospital_id != hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied"
        )
    
    # Get hospital email
    hospital_result = supabase.table("hospitals").select("email").eq("id", hospital_id).execute()
    if not hospital_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    
    hospital_email = hospital_result.data[0]["email"]
    
    # Import email service
    from services.email_service import send_email
    
    # Send test email
    success = await send_email(
        to_email=hospital_email,
        subject="SMTP Test Email - Hospital Booking System",
        body_text="This is a test email to verify your SMTP settings are configured correctly.\n\nIf you received this email, your SMTP configuration is working!",
        body_html="<html><body><h2>SMTP Test Email</h2><p>This is a test email to verify your SMTP settings are configured correctly.</p><p><strong>If you received this email, your SMTP configuration is working!</strong></p></body></html>",
        hospital_id=hospital_id
    )
    
    # Log audit event
    from services.audit_logger import log_audit_event
    log_audit_event(
        event_type="message_send",
        user_id=current_user["id"],
        user_role=current_user["role"],
        action=f"SMTP test email sent to {hospital_email}",
        resource_type="hospital",
        resource_id=hospital_id,
        details={"test_email": True, "success": success}
    )
    
    return {
        "success": success,
        "message": "Test email sent successfully" if success else "Failed to send test email. Please check your SMTP settings.",
        "hospital_id": hospital_id,
        "test_email": hospital_email
    }

