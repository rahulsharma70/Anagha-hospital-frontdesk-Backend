from fastapi import APIRouter, Depends, HTTPException, status
from models import UserRole
# Note: User SQLAlchemy model removed - using Supabase now
from auth import get_current_user
import json
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Verify user is admin/doctor"""
    if current_user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.post("/update-pricing")
def update_pricing(
    pricing_data: dict,
    admin_user: dict = Depends(get_admin_user)
):
    """Update pricing configuration"""
    try:
        # Validate pricing data structure
        required_fields = ["plans", "annual_discount", "currency", "currency_symbol"]
        for field in required_fields:
            if field not in pricing_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Validate plans
        if not isinstance(pricing_data["plans"], list) or len(pricing_data["plans"]) == 0:
            raise HTTPException(status_code=400, detail="At least one plan is required")
        
        for plan in pricing_data["plans"]:
            required_plan_fields = ["name", "price", "period", "description", "features"]
            for field in required_plan_fields:
                if field not in plan:
                    raise HTTPException(status_code=400, detail=f"Plan missing required field: {field}")
        
        # Save to file
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent
        config_path = backend_dir / "pricing_config.json"
        with open(config_path, "w") as f:
            json.dump(pricing_data, f, indent=2)
        
        return {"message": "Pricing updated successfully", "pricing": pricing_data}
    
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Pricing config file not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating pricing: {str(e)}")

@router.get("/pricing")
def get_pricing(admin_user: dict = Depends(get_admin_user)):
    """Get current pricing configuration"""
    try:
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent
        config_path = backend_dir / "pricing_config.json"
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default if file doesn't exist
        return {
            "plans": [
                {
                    "name": "Starter",
                    "price": "999",
                    "period": "month",
                    "description": "Perfect for small clinics",
                    "features": ["Up to 5 doctors", "Unlimited appointments", "Basic scheduling", "Email support"],
                    "popular": False
                }
            ],
            "annual_discount": 20,
            "currency": "INR",
            "currency_symbol": "₹"
        }

@router.get("/pricing/public")
def get_public_pricing():
    """Get pricing plans for public (hospital registration) - no auth required"""
    try:
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent
        config_path = backend_dir / "pricing_config.json"
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Return default pricing plans matching the frontend Pricing component
        return {
            "plans": [
                {
                    "name": "Starter",
                    "description": "For 1 Doctor / 1 Hospital",
                    "installationPrice": 5000,
                    "monthlyPrice": 1000,
                    "features": [
                        "1 Doctor profile",
                        "1 Hospital",
                        "Appointment management",
                        "Email reminders",
                        "Basic analytics",
                        "Email support",
                    ],
                    "popular": False,
                },
                {
                    "name": "Professional",
                    "description": "For 5 Doctors in 1 Hospital",
                    "installationPrice": 10000,
                    "monthlyPrice": 2000,
                    "features": [
                        "Up to 5 Doctor profiles",
                        "1 Hospital",
                        "SMS & Email reminders",
                        "Advanced analytics",
                        "Custom booking page",
                        "Payment integration",
                        "Priority support",
                    ],
                    "popular": True,
                },
                {
                    "name": "Enterprise",
                    "description": "For 10 Doctors & 5 Hospitals",
                    "installationPrice": 20000,
                    "monthlyPrice": 5000,
                    "features": [
                        "Up to 10 Doctor profiles",
                        "Up to 5 Hospitals (same ownership)",
                        "Multi-location support",
                        "Custom integrations",
                        "Dedicated account manager",
                        "24/7 phone support",
                        "White-label option",
                    ],
                    "popular": False,
                },
            ],
            "currency": "INR",
            "currency_symbol": "₹"
        }



