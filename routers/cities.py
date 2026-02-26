from fastapi import APIRouter, HTTPException, Query
from services.city_service import CityService
from typing import Optional, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cities", tags=["cities"])

# In-memory cache for city searches
city_search_cache = {}
CACHE_TTL = 3600  # Cache for 1 hour
cache_timestamps = {}

def get_cached_cities(query: str) -> Optional[List[dict]]:
    cache_key = query.lower()
    if cache_key in city_search_cache:
        if cache_key in cache_timestamps:
            age = (datetime.now() - cache_timestamps[cache_key]).total_seconds()
            if age < CACHE_TTL:
                return city_search_cache[cache_key]
            else:
                del city_search_cache[cache_key]
                del cache_timestamps[cache_key]
    return None

def set_cached_cities(query: str, cities: List[dict]):
    cache_key = query.lower()
    city_search_cache[cache_key] = cities
    cache_timestamps[cache_key] = datetime.now()

@router.get("/search")
async def search_cities(q: str = Query("", description="Search query for city name")):
    try:
        query = q.strip().lower()
        if len(query) < 2:
            return {"cities": [], "source": "empty_query"}
        
        cached_results = get_cached_cities(query)
        if cached_results is not None:
            return {"cities": cached_results, "source": "cache", "cached": True}
        
        matching_cities = CityService.query_city_database(query)
        if matching_cities:
            set_cached_cities(query, matching_cities)
            
        return {"cities": matching_cities, "source": "database", "cached": False}
    except Exception as e:
        logger.error(f"Error searching cities: {e}")
        return {"cities": [], "source": "error", "error": str(e)}

@router.get("/popular")
async def get_popular_cities():
    try:
        cache_key = "popular"
        cached = get_cached_cities(cache_key)
        if cached:
            return {"cities": cached, "source": "cache", "cached": True}
        
        popular = CityService.get_popular_cities_from_db()
        set_cached_cities(cache_key, [{"city_name": city} for city in popular])
        return {"cities": popular, "source": "database", "cached": False}
    except Exception as e:
        logger.error(f"Error getting popular cities: {e}")
        return {"cities": [], "source": "fallback"}

@router.post("/add")
async def add_new_city(city_data: dict):
    try:
        city_name = city_data.get("city_name", "").strip()
        if not city_name:
            raise HTTPException(status_code=400, detail="City name is required")
            
        result = CityService.add_new_city(city_data)
        
        if result["message"] == "City added successfully":
            cache_key = city_name.lower()
            if cache_key in city_search_cache:
                del city_search_cache[cache_key]
                if cache_key in cache_timestamps:
                    del cache_timestamps[cache_key]
                    
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
