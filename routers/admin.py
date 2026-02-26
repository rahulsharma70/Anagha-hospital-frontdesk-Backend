from fastapi import APIRouter, Depends, HTTPException
from dependencies.auth import get_current_admin
from services.admin_service import AdminService
import json

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/update-pricing")
def update_pricing(pricing_data: dict, admin_user: dict = Depends(get_current_admin)):
    try:
        required_fields = ["plans", "annual_discount", "currency", "currency_symbol"]
        for field in required_fields:
            if field not in pricing_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        if not isinstance(pricing_data["plans"], list) or len(pricing_data["plans"]) == 0:
            raise HTTPException(status_code=400, detail="At least one plan is required")
        
        for plan in pricing_data["plans"]:
            required_plan_fields = ["name", "price", "period", "description", "features"]
            for field in required_plan_fields:
                if field not in plan:
                    raise HTTPException(status_code=400, detail=f"Plan missing required field: {field}")
        
        return AdminService.update_pricing(pricing_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating pricing: {str(e)}")

@router.get("/pricing")
def get_pricing(admin_user: dict = Depends(get_current_admin)):
    return AdminService.get_pricing()

@router.get("/pricing/public")
def get_public_pricing():
    return AdminService.get_public_pricing()
