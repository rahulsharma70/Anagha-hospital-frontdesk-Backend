from fastapi import APIRouter, Depends, BackgroundTasks
from dependencies.auth import get_current_user, get_current_doctor
from services.appointment_service import AppointmentService
from schemas import AppointmentCreate, GuestAppointmentCreate
from typing import List
from datetime import date
import logging
from fastapi_limiter.depends import RateLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/appointments", tags=["appointments"])

@router.post("/book", response_model=dict, dependencies=[Depends(RateLimiter(times=3, seconds=60))])
async def book_appointment(appointment: AppointmentCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    result = AppointmentService.process_booking(appointment.model_dump(), current_user, is_guest=False)
    # Background tasks like whatsapp can be queued here from result returned values
    apt = result["appointment"]
    return {
        "id": apt["id"],
        "user_id": apt["user_id"],
        "doctor_id": apt["doctor_id"],
        "hospital_id": apt.get("hospital_id"),
        "date": apt["date"],
        "time_slot": apt["time_slot"],
        "status": apt["status"],
        "user_name": current_user.get("name", ""),
        "doctor_name": result["doctor"].get("name", ""),
        "hospital_name": result["hospital"].get("name", "")
    }

@router.post("/book-guest", response_model=dict, dependencies=[Depends(RateLimiter(times=2, seconds=120))])
async def book_appointment_guest(appointment: GuestAppointmentCreate, background_tasks: BackgroundTasks):
    result = AppointmentService.process_booking(appointment.model_dump(), {}, is_guest=True)
    apt = result["appointment"]
    return {
        "id": apt["id"],
        "message": "Appointment booked successfully. Please complete payment to confirm.",
        "status": apt["status"],
        "doctor_id": apt["doctor_id"],
        "hospital_id": apt["hospital_id"],
        "date": apt["date"],
        "time_slot": apt["time_slot"],
        "is_guest": True
    }

@router.get("/my-appointments")
async def get_my_appointments(current_user: dict = Depends(get_current_user)):
    return AppointmentService.get_user_appointments(current_user["id"])

@router.get("/doctor-appointments")
async def get_doctor_appointments(current_doctor: dict = Depends(get_current_doctor)):
    return AppointmentService.get_doctor_appointments(current_doctor["user_id"])

@router.put("/{appointment_id}/confirm")
async def confirm_appointment(appointment_id: int, current_doctor: dict = Depends(get_current_doctor)):
    AppointmentService.update_status(appointment_id, current_doctor["user_id"], current_doctor.get("role", "doctor"), "confirm")
    return {"message": "Appointment confirmed"}

@router.put("/{appointment_id}/cancel")
async def cancel_appointment(appointment_id: int, current_user: dict = Depends(get_current_user)):
    AppointmentService.update_status(appointment_id, current_user["id"], current_user.get("role", "patient"), "cancel")
    return {"message": "Appointment cancelled"}

@router.put("/{appointment_id}/mark-visited")
async def mark_appointment_visited(appointment_id: int, current_doctor: dict = Depends(get_current_doctor)):
    AppointmentService.update_status(appointment_id, current_doctor["user_id"], current_doctor.get("role", "doctor"), "mark_visited")
    return {"message": "Appointment marked as visited", "visit_date": date.today().isoformat()}

@router.get("/available-slots")
async def get_available_slots(doctor_id: int, date: str, current_user: dict = Depends(get_current_user)):
    return AppointmentService.get_available_slots(doctor_id, date)
