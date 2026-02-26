import secrets
from datetime import date as date_obj, datetime
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from core.database import get_supabase
from core.security import get_password_hash

class AppointmentService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @staticmethod
    def is_valid_time_slot(time_slot: str) -> bool:
        valid_slots = [
            "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
            "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"
        ]
        return time_slot in valid_slots

    @classmethod
    def process_booking(cls, appointment_data: Dict[str, Any], current_user: Dict[str, Any], is_guest: bool = False) -> Dict[str, Any]:
        supabase = cls._get_db()

        if not cls.is_valid_time_slot(appointment_data["time_slot"]):
            raise HTTPException(status_code=400, detail="Invalid time slot")

        if appointment_data["date"] < date_obj.today():
            raise HTTPException(status_code=400, detail="Cannot book appointment for past dates")

        # Verify doctor
        doctor_result = supabase.table("doctors").select("*").eq("id", appointment_data["doctor_id"]).eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(status_code=404, detail="Doctor not found")
        doctor = doctor_result.data[0]
        
        hospital_id = doctor.get("hospital_id")
        if not hospital_id:
            raise HTTPException(status_code=400, detail="Doctor is not associated with any hospital")

        user_hospital_id = current_user.get("hospital_id")
        if not is_guest and user_hospital_id and user_hospital_id != hospital_id:
            raise HTTPException(status_code=400, detail="Doctor does not belong to your selected hospital")

        # Verify hospital
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data or hospital_result.data[0].get("status") not in ("approved", "ACTIVE"):
            raise HTTPException(status_code=400, detail="Hospital not found or not approved")

        hospital = hospital_result.data[0]

        # Check existing booking
        existing_result = supabase.table("appointments").select("*").eq(
            "doctor_id", appointment_data["doctor_id"]
        ).eq("date", str(appointment_data["date"])).eq("time_slot", appointment_data["time_slot"]).neq(
            "status", "cancelled"
        ).execute()

        if existing_result.data:
            raise HTTPException(status_code=400, detail="Time slot already booked")

        user_id = current_user.get("id")
        if is_guest:
            # Handle guest creation
            patient_phone = appointment_data.get("patient_phone", "").strip()
            patient_result = supabase.table("users").select("id").eq("mobile", patient_phone).eq("role", "patient").execute()
            if patient_result.data:
                user_id = patient_result.data[0]["id"]
            else:
                pwd = secrets.token_urlsafe(32)
                guest_user = {
                    "name": appointment_data.get("patient_name", "").strip(),
                    "mobile": patient_phone,
                    "role": "patient",
                    "is_active": False,
                    "password_hash": get_password_hash(pwd)
                }
                guest_result = supabase.table("users").insert(guest_user).execute()
                user_id = guest_result.data[0]["id"]

        appointment_record = {
            "user_id": user_id,
            "doctor_id": appointment_data["doctor_id"],
            "hospital_id": hospital_id,
            "date": str(appointment_data["date"]),
            "time_slot": appointment_data["time_slot"],
            "status": "pending",
            "reason": appointment_data.get("reason", "")
        }

        result = supabase.table("appointments").insert(appointment_record).execute()
        db_appointment = result.data[0]

        return {
            "appointment": db_appointment,
            "hospital": hospital,
            "doctor": doctor,
            "user_id": user_id
        }

    @classmethod
    def get_user_appointments(cls, user_id: int) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("appointments").select("*, doctors(name, mobile), hospitals(name)").eq("user_id", user_id).order("date").order("time_slot").execute()
        return result.data if result.data else []

    @classmethod
    def get_doctor_appointments(cls, doctor_id: int) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("appointments").select("*, users(name, mobile), hospitals(name)").eq("doctor_id", doctor_id).order("date").order("time_slot").execute()
        return result.data if result.data else []

    @classmethod
    def update_status(cls, appointment_id: int, user_id: int, user_role: str, action: str) -> Dict[str, Any]:
        supabase = cls._get_db()
        
        apt_res = supabase.table("appointments").select("*").eq("id", appointment_id).execute()
        if not apt_res.data:
            raise HTTPException(status_code=404, detail="Appointment not found")
        apt = apt_res.data[0]

        # Auth checks
        if action == "cancel":
            if apt["user_id"] != user_id and apt["doctor_id"] != user_id and user_role != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
            update_data = {"status": "cancelled"}
        elif action == "confirm":
            if apt["doctor_id"] != user_id and user_role != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
            update_data = {"status": "confirmed"}
        elif action == "mark_visited":
            if apt["doctor_id"] != user_id and user_role != "admin":
                raise HTTPException(status_code=403, detail="Not authorized")
            update_data = {"status": "completed", "visit_date": date_obj.today().isoformat()}
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        res = supabase.table("appointments").update(update_data).eq("id", appointment_id).execute()
        return res.data[0] if res.data else {}

    @classmethod
    def get_available_slots(cls, doctor_id: int, date_str: str) -> Dict[str, Any]:
        supabase = cls._get_db()
        
        doc_res = supabase.table("doctors").select("*").eq("id", doctor_id).eq("is_active", True).execute()
        if not doc_res.data:
            raise HTTPException(status_code=404, detail="Doctor not found")
            
        all_slots = [
            "09:30", "10:00", "10:30", "11:00", "11:30", "12:00",
            "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "18:00", "18:30", "19:00", "19:30", "20:00", "20:30"
        ]
        
        booked_result = supabase.table("appointments").select("time_slot").eq(
            "doctor_id", doctor_id
        ).eq("date", date_str).neq("status", "cancelled").execute()
        
        booked_slots = [a["time_slot"] for a in (booked_result.data or [])]
        available_slots = [s for s in all_slots if s not in booked_slots]
        
        return {
            "doctor_id": doctor_id,
            "doctor_name": doc_res.data[0]["name"],
            "date": date_str,
            "available_slots": available_slots,
            "booked_slots": booked_slots
        }
