from typing import Dict, Any, List
from datetime import date
from fastapi import HTTPException
from core.database import get_supabase

class OperationService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @classmethod
    def process_booking(cls, operation_data: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        supabase = cls._get_db()

        if operation_data["date"] < date.today():
            raise HTTPException(status_code=400, detail="Cannot book operation for past dates")

        # Verify doctor
        doctor_result = supabase.table("doctors").select("*").eq("id", operation_data["doctor_id"]).eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(status_code=404, detail="Doctor not found")
        doctor = doctor_result.data[0]

        hospital_id = doctor.get("hospital_id")
        user_hospital_id = current_user.get("hospital_id")
        
        if not hospital_id:
            raise HTTPException(status_code=400, detail="Doctor is not associated with any hospital")

        if user_hospital_id and user_hospital_id != hospital_id:
            raise HTTPException(status_code=400, detail="Doctor does not belong to your selected hospital")

        # Verify hospital is approved
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data or hospital_result.data[0].get("status") != "approved":
            raise HTTPException(status_code=400, detail="Cannot book operation with unapproved hospital")
        hospital = hospital_result.data[0]

        operation_record = {
            "patient_id": current_user["id"],
            "specialty": str(operation_data.get("specialty")),
            "operation_date": str(operation_data["date"]),
            "doctor_id": operation_data["doctor_id"],
            "hospital_id": hospital_id,
            "status": "pending",
            "notes": operation_data.get("notes")
        }

        result = supabase.table("operations").insert(operation_record).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create operation")
        
        db_op = result.data[0]

        return {
            "operation": db_op,
            "hospital": hospital,
            "doctor": doctor
        }

    @classmethod
    def get_patient_operations(cls, patient_id: int) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("operations").select(
            "*, doctors(name, mobile), hospitals(name)"
        ).eq("patient_id", patient_id).order("operation_date").execute()
        return result.data if result.data else []

    @classmethod
    def get_doctor_operations(cls, doctor_id: int) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("operations").select(
            "*, users(name, mobile), hospitals(name)"
        ).eq("doctor_id", doctor_id).order("operation_date").execute()
        return result.data if result.data else []

    @classmethod
    def get_operations_by_specialty(cls, specialty: str, user_id: int, is_doctor: bool) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        q = supabase.table("operations").select("*, doctors(name), users(name), hospitals(name)").eq("specialty", specialty)
        
        if is_doctor:
            doctor_check = supabase.table("doctors").select("id").eq("user_id", user_id).eq("is_active", True).execute()
            if not doctor_check.data:
                return []
            q = q.eq("doctor_id", doctor_check.data[0]["id"])
        else:
            q = q.eq("patient_id", user_id)
            
        result = q.order("operation_date").execute()
        return result.data if result.data else []

    @classmethod
    def update_status(cls, operation_id: int, user_id: int, action: str) -> Dict[str, Any]:
        supabase = cls._get_db()
        
        op_res = supabase.table("operations").select("*").eq("id", operation_id).execute()
        if not op_res.data:
            raise HTTPException(status_code=404, detail="Operation not found")
        op = op_res.data[0]

        if action == "cancel":
            if op["patient_id"] != user_id and op["doctor_id"] != user_id:
                raise HTTPException(status_code=403, detail="Not authorized")
            status = "cancelled"
        elif action == "confirm":
            # Note: Actually it checks if the current doctor's `id` is `doctor_id`.
            if op["doctor_id"] != user_id:  # where user_id here represents doctor_id
                raise HTTPException(status_code=403, detail="Not authorized")
            status = "confirmed"
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        res = supabase.table("operations").update({"status": status}).eq("id", operation_id).execute()
        return res.data[0] if res.data else {}
