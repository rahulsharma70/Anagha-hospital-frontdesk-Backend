from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from datetime import date, datetime
from database import get_supabase
from schemas import AppointmentCreate, AppointmentResponse
from auth import get_current_user, get_current_doctor
from typing import List
import logging

# Import services
from services.csv_service import save_appointment_csv
from services.whatsapp_service import send_whatsapp_message_by_hospital_id
from services.message_templates import get_confirmation_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

def is_valid_time_slot(time_slot: str) -> bool:
    """Validate time slot is within allowed hours"""
    valid_slots = [
        "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
        "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
        "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"
    ]
    return time_slot in valid_slots

@router.post("/book", response_model=dict)
def book_appointment(
    appointment: AppointmentCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Book an appointment (for patients and pharma professionals) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Validate time slot
        if not is_valid_time_slot(appointment.time_slot):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid time slot. Must be between 9:30 AM - 3:30 PM or 6:00 PM - 8:30 PM"
            )
        
        # Check if date is in the past
        if appointment.date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book appointment for past dates"
            )
        
        # Verify doctor exists and is a doctor
        doctor_result = supabase.table("users").select("*").eq("id", appointment.doctor_id).eq("role", "doctor").eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        doctor = doctor_result.data[0]
        
        # Validate doctor-hospital relationship
        doctor_hospital_id = doctor.get("hospital_id")
        user_hospital_id = current_user.get("hospital_id")
        
        # Doctor must have a hospital_id
        if not doctor_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is not associated with any hospital"
            )
        
        # If user has hospital_id, it must match doctor's hospital_id
        if user_hospital_id and user_hospital_id != doctor_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor does not belong to your selected hospital"
            )
        
        # Use doctor's hospital_id (required)
        hospital_id = doctor_hospital_id
        
        # Verify hospital exists and is approved
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        hospital = hospital_result.data[0]
        
        # Ensure hospital is approved
        if hospital.get("status") != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book appointment with unapproved hospital"
            )
        
        # Check if time slot is already booked for this doctor on this date
        existing_result = supabase.table("appointments").select("*").eq(
            "doctor_id", appointment.doctor_id
        ).eq("date", str(appointment.date)).eq("time_slot", appointment.time_slot).neq(
            "status", "cancelled"
        ).execute()
        
        if existing_result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time slot already booked"
            )
        
        # Create appointment record
        appointment_record = {
            "user_id": current_user["id"],
            "doctor_id": appointment.doctor_id,
            "hospital_id": hospital_id,
            "date": str(appointment.date),
            "time_slot": appointment.time_slot,
            "status": "pending",
            "reason": getattr(appointment, 'reason', None)
        }
        
        result = supabase.table("appointments").insert(appointment_record).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create appointment"
            )
        
        db_appointment = result.data[0]
        
        # Save to CSV and send WhatsApp (background tasks)
        if hospital_id and hospital:
            csv_data = {
                "name": current_user.get("name", ""),
                "mobile": current_user.get("mobile", ""),
                "date": str(appointment.date),
                "time_slot": appointment.time_slot,
                "doctor": doctor.get("name", ""),
                "specialty": "",
                "followup_date": ""
            }
            
            # Save to CSV in background
            background_tasks.add_task(save_appointment_csv, hospital_id, csv_data)
            
            # Send WhatsApp confirmation if enabled
            if hospital.get("whatsapp_enabled") == "true" or hospital.get("whatsapp_enabled") is True:
                message = get_confirmation_message(
                    patient_name=current_user.get("name", ""),
                    doctor_name=doctor.get("name", ""),
                    date=str(appointment.date),
                    time_slot=appointment.time_slot,
                    hospital_name=hospital.get("name", ""),
                    specialty=None,
                    custom_template=hospital.get("whatsapp_confirmation_template")
                )
                background_tasks.add_task(
                    send_whatsapp_message_by_hospital_id,
                    hospital_id=hospital_id,
                    mobile=current_user.get("mobile", ""),
                    message=message
                )
        
        # Return response with user and doctor names
        return {
            "id": db_appointment["id"],
            "user_id": db_appointment["user_id"],
            "doctor_id": db_appointment["doctor_id"],
            "hospital_id": db_appointment.get("hospital_id", hospital_id),  # Include mandatory hospital_id
            "date": db_appointment["date"],
            "time_slot": db_appointment["time_slot"],
            "status": db_appointment["status"],
            "created_at": db_appointment.get("created_at", datetime.now().isoformat()),
            "user_name": current_user.get("name", ""),
            "doctor_name": doctor.get("name", ""),
            "hospital_name": hospital.get("name", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error booking appointment: {str(e)}"
        )

@router.get("/my-appointments", response_model=List[dict])
def get_my_appointments(current_user: dict = Depends(get_current_user)):
    """Get all appointments for current user - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("appointments").select("*").eq("user_id", current_user["id"]).order("date", desc=False).order("time_slot", desc=False).execute()
        
        appointments = []
        for apt in (result.data or []):
            # Fetch doctor info
            doctor_info = {}
            if apt.get("doctor_id"):
                doctor_result = supabase.table("users").select("id, name, mobile").eq("id", apt["doctor_id"]).execute()
                if doctor_result.data:
                    doctor_info = doctor_result.data[0]
            
            # Fetch hospital info
            hospital_info = {}
            if apt.get("hospital_id"):
                hospital_result = supabase.table("hospitals").select("id, name").eq("id", apt["hospital_id"]).execute()
                if hospital_result.data:
                    hospital_info = hospital_result.data[0]
            
            appointments.append({
                "id": apt["id"],
                "user_id": apt["user_id"],
                "doctor_id": apt["doctor_id"],
                "date": apt["date"],
                "time_slot": apt["time_slot"],
                "status": apt["status"],
                "created_at": apt.get("created_at", ""),
                "user_name": current_user.get("name", ""),
                "doctor_name": doctor_info.get("name", "Unknown"),
                "hospital_name": hospital_info.get("name", "Unknown Hospital")
            })
        
        return appointments
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching appointments: {str(e)}"
        )

@router.get("/doctor-appointments", response_model=List[dict])
def get_doctor_appointments(current_doctor: dict = Depends(get_current_doctor)):
    """Get all appointments for current doctor - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("appointments").select("*").eq("doctor_id", current_doctor["id"]).order("date", desc=False).order("time_slot", desc=False).execute()
        
        appointments = []
        for apt in (result.data or []):
            # Fetch user info
            user_info = {}
            if apt.get("user_id"):
                user_result = supabase.table("users").select("id, name, mobile").eq("id", apt["user_id"]).execute()
                if user_result.data:
                    user_info = user_result.data[0]
            
            # Fetch hospital info
            hospital_info = {}
            if apt.get("hospital_id"):
                hospital_result = supabase.table("hospitals").select("id, name").eq("id", apt["hospital_id"]).execute()
                if hospital_result.data:
                    hospital_info = hospital_result.data[0]
            
            appointments.append({
                "id": apt["id"],
                "user_id": apt["user_id"],
                "doctor_id": apt["doctor_id"],
                "date": apt["date"],
                "time_slot": apt["time_slot"],
                "status": apt["status"],
                "created_at": apt.get("created_at", ""),
                "user_name": user_info.get("name", "Unknown"),
                "doctor_name": current_doctor.get("name", ""),
                "hospital_name": hospital_info.get("name", "Unknown Hospital")
            })
        
        return appointments
    except Exception as e:
        logger.error(f"Error fetching doctor appointments: {e}")
        return []

@router.put("/{appointment_id}/confirm")
def confirm_appointment(
    appointment_id: int,
    current_doctor: dict = Depends(get_current_doctor)
):
    """Confirm an appointment (doctor only) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check appointment exists and belongs to doctor
        appointment_result = supabase.table("appointments").select("*").eq(
            "id", appointment_id
        ).eq("doctor_id", current_doctor["id"]).execute()
        
        if not appointment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Update status
        update_result = supabase.table("appointments").update({
            "status": "confirmed"
        }).eq("id", appointment_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to confirm appointment"
            )
        
        return {"message": "Appointment confirmed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error confirming appointment: {str(e)}"
        )

@router.put("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Cancel an appointment - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check appointment exists
        appointment_result = supabase.table("appointments").select("*").eq("id", appointment_id).execute()
        
        if not appointment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        appointment = appointment_result.data[0]
        
        # Only allow cancellation by the user who booked it or the doctor
        if appointment["user_id"] != current_user["id"] and appointment["doctor_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this appointment"
            )
        
        # Update status
        update_result = supabase.table("appointments").update({
            "status": "cancelled"
        }).eq("id", appointment_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel appointment"
            )
        
        return {"message": "Appointment cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling appointment: {str(e)}"
        )

@router.put("/{appointment_id}/mark-visited")
def mark_appointment_visited(
    appointment_id: int,
    current_doctor: dict = Depends(get_current_doctor)
):
    """Mark appointment as visited (doctor only) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check appointment exists and belongs to doctor
        appointment_result = supabase.table("appointments").select("*").eq(
            "id", appointment_id
        ).eq("doctor_id", current_doctor["id"]).execute()
        
        if not appointment_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )
        
        # Update status
        update_result = supabase.table("appointments").update({
            "status": "completed",
            "visit_date": date.today().isoformat()
        }).eq("id", appointment_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark appointment as visited"
            )
        
        return {
            "message": "Appointment marked as visited",
            "visit_date": date.today().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking appointment as visited: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error marking appointment as visited: {str(e)}"
        )

@router.get("/available-slots")
def get_available_slots(
    doctor_id: int,
    date: str,  # Changed from date type to str for Supabase compatibility
    current_user: dict = Depends(get_current_user)
):
    """Get available time slots for a doctor on a specific date - using Supabase. Requires authentication."""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Verify doctor exists
        doctor_result = supabase.table("users").select("*").eq("id", doctor_id).eq("role", "doctor").eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        doctor = doctor_result.data[0]
        
        # Get all time slots
        all_slots = [
            "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
            "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"
        ]
        
        # Get booked appointments
        booked_result = supabase.table("appointments").select("time_slot").eq(
            "doctor_id", doctor_id
        ).eq("date", date).neq("status", "cancelled").execute()
        
        booked_slots = [apt["time_slot"] for apt in (booked_result.data or [])]
        available_slots = [slot for slot in all_slots if slot not in booked_slots]
        
        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.get("name", ""),
            "date": date,
            "available_slots": available_slots,
            "booked_slots": booked_slots
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching available slots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching available slots: {str(e)}"
        )
