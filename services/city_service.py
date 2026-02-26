from typing import List, Dict, Any
from core.database import get_supabase

class CityService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @classmethod
    def query_city_database(cls, query: str) -> List[Dict[str, Any]]:
        supabase = cls._get_db()
        res = supabase.table("cities").select("city_name, state_name").ilike("city_name", f"%{query}%").eq("is_active", True).limit(20).execute()
        
        cities = [{"city_name": c.get("city_name", ""), "state_name": c.get("state_name", "")} for c in (res.data or [])]
        
        cities.sort(key=lambda x: (
            0 if x["city_name"].lower().startswith(query.lower()) else 1,
            x["city_name"].lower().index(query.lower()) if query.lower() in x["city_name"].lower() else 999,
            len(x["city_name"])
        ))
        
        return cities[:20]

    @classmethod
    def get_popular_cities_from_db(cls) -> List[str]:
        supabase = cls._get_db()
        popular = [
            "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata",
            "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Kanpur",
            "Nagpur", "Indore", "Thane", "Bhopal"
        ]
        res = supabase.table("cities").select("city_name").eq("is_active", True).limit(15).execute()
        if res.data:
            popular = [city["city_name"] for city in res.data[:15]]
        return popular

    @classmethod
    def add_new_city(cls, city_data: Dict[str, Any]) -> Dict[str, Any]:
        supabase = cls._get_db()
        city_name = city_data.get("city_name", "").strip()
        existing = supabase.table("cities").select("id").eq("city_name", city_name).execute()
        
        if existing.data:
            return {"message": "City already exists", "city_name": city_name, "id": existing.data[0]["id"]}
            
        new_city = {
            "city_name": city_name,
            "state_name": city_data.get("state_name", "").strip() or None,
            "district_name": city_data.get("district_name", "").strip() or None,
            "pincode": city_data.get("pincode", "").strip() or None,
            "source": "manual",
            "is_active": True
        }
        res = supabase.table("cities").insert(new_city).execute()
        return {"message": "City added successfully", "city_name": city_name, "id": res.data[0]["id"]}
