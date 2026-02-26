from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from core.database import get_supabase
from datetime import datetime

class HospitalService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @classmethod
    def register_hospital(cls, hospital_data: Dict[str, Any], payment_id: int) -> Dict[str, Any]:
        supabase = cls._get_db()

        # Check Payment Status
        payment_check = supabase.table("payments").select("*").eq("id", payment_id).execute()
        if not payment_check.data or payment_check.data[0].get("status") != "COMPLETED":
            raise HTTPException(status_code=400, detail="Invalid or incomplete payment")
        
        pay_data = payment_check.data[0]
        if pay_data.get("hospital_id"):
            raise HTTPException(status_code=400, detail="Payment already used")

        # Check email exists
        if supabase.table("hospitals").select("id").eq("email", hospital_data["email"]).execute().data:
            raise HTTPException(status_code=400, detail="Hospital email already registered")

        hospital_data["status"] = "pending"
        res = supabase.table("hospitals").insert(hospital_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Database insertion failed")
            
        hospital = res.data[0]
        
        # Link payment back
        supabase.table("payments").update({"hospital_id": hospital["id"]}).eq("id", payment_id).execute()

        return hospital

    @classmethod
    def get_public_hospitals(cls, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        q = supabase.table("hospitals").select("*")
        if status_filter:
            q = q.eq("status", status_filter)
        res = q.order("created_at", desc=True).execute()
        return res.data if res.data else []
        
    @classmethod
    def get_hospital_by_id(cls, hospital_id: int) -> Dict[str, Any]:
        supabase = cls._get_db()
        res = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Hospital not found")
        return res.data[0]

    @classmethod
    def update_status(cls, hospital_id: int, new_status: str) -> Dict[str, Any]:
        supabase = cls._get_db()
        
        if new_status not in ["approved", "rejected"]:
            raise HTTPException(status_code=400, detail="Invalid status")
            
        update_data = {"status": new_status, "approved_date": datetime.utcnow().isoformat() if new_status == "approved" else None}
        res = supabase.table("hospitals").update(update_data).eq("id", hospital_id).execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="Hospital not found or update failed")
        return res.data[0]

    @classmethod
    def update_whatsapp_settings(cls, hospital_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        supabase = cls._get_db()
        res = supabase.table("hospitals").update(updates).eq("id", hospital_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Hospital not found")
        return res.data[0]

    @classmethod
    def update_smtp_settings(cls, hospital_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        supabase = cls._get_db()
        res = supabase.table("hospitals").update(updates).eq("id", hospital_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Hospital not found")
        return res.data[0]
