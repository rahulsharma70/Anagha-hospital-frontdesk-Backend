from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from core.database import get_supabase

class DoctorService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @classmethod
    def register_doctor(cls, doctor_data: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a doctor and creates their user auth record"""
        supabase = cls._get_db()
        
        # Verify hospital exists and is active
        hospital = supabase.table("hospitals").select("status").eq("id", doctor_data["hospital_id"]).execute()
        if not hospital.data or hospital.data[0].get("status") != "ACTIVE":
            raise HTTPException(status_code=400, detail="Associated hospital is not active")

        # Create auth user first (this will just serve as login credential)
        user_result = supabase.table("users").insert(user_data).execute()
        if not user_result.data:
            raise HTTPException(status_code=500, detail="Failed to create auth user for doctor")
            
        user_id = user_result.data[0]["id"]
        doctor_data["user_id"] = user_id
        
        # Insert Doctor details - initially PENDING_APPROVAL based on requirement
        doctor_data["is_active"] = False
        doctor_data["status"] = "PENDING_APPROVAL"
        
        doc_result = supabase.table("doctors").insert(doctor_data).execute()
        
        if not doc_result.data:
            supabase.table("users").delete().eq("id", user_id).execute()
            raise HTTPException(status_code=500, detail="Failed to create doctor profile")
            
        return doc_result.data[0]
        
    @classmethod
    def get_public_doctors(cls, query: Optional[str] = None) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        db_query = supabase.table("doctors").select("*").eq("is_active", True)
        if query:
            db_query = db_query.ilike("name", f"%{query}%")
        result = db_query.execute()
        return result.data if result.data else []
        
    @classmethod
    def get_cities(cls) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        result = supabase.table("hospitals").select("city, state").not_.is_("city", "null").execute()
        if not result.data: return []
        
        cities = {}
        for h in result.data:
            city_key = f"{h.get('city')}_{h.get('state')}"
            if city_key not in cities:
                cities[city_key] = {"name": h.get("city"), "state": h.get("state")}
        return list(cities.values())
