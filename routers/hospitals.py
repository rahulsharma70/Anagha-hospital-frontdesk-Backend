from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from schemas import HospitalCreate
from services.hospital_service import HospitalService
from dependencies.auth import get_current_user, get_current_admin
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])

@router.post("/register", response_model=dict)
def register_hospital(hospital: HospitalCreate, background_tasks: BackgroundTasks):
    if not hospital.payment_id:
        raise HTTPException(status_code=400, detail="Payment is required")
        
    data = hospital.model_dump(exclude_unset=True, exclude={'payment_id'})
    result = HospitalService.register_hospital(data, hospital.payment_id)
    
    # Can dispatch background emails here using `background_tasks.add_task`
    return {
        "message": "Hospital registered successfully. Registration request has been sent for admin approval.",
        "hospital_id": result["id"],
        "status": result["status"]
    }

@router.get("/", response_model=List[dict])
def get_hospitals(status_filter: Optional[str] = None):
    return HospitalService.get_public_hospitals(status_filter)

@router.get("/approved", response_model=List[dict])
def get_approved_hospitals():
    return HospitalService.get_public_hospitals("approved")

@router.get("/pending", response_model=List[dict])
def get_pending_hospitals(admin: dict = Depends(get_current_admin)):
    return HospitalService.get_public_hospitals("pending")

@router.get("/{hospital_id}", response_model=dict)
def get_hospital_by_id(hospital_id: int):
    return HospitalService.get_hospital_by_id(hospital_id)

@router.put("/{hospital_id}/approve")
def approve_hospital(hospital_id: int, admin: dict = Depends(get_current_admin)):
    hosp = HospitalService.update_status(hospital_id, "approved")
    return {"message": "Hospital approved", "hospital": hosp}

@router.put("/{hospital_id}/reject")
def reject_hospital(hospital_id: int, admin: dict = Depends(get_current_admin)):
    hosp = HospitalService.update_status(hospital_id, "rejected")
    return {"message": "Hospital rejected", "hospital": hosp}

class WhatsAppSettingsUpdate(BaseModel):
    whatsapp_enabled: Optional[str] = None
    whatsapp_confirmation_template: Optional[str] = None
    whatsapp_followup_template: Optional[str] = None

@router.put("/{hospital_id}/whatsapp-settings")
def update_whatsapp_settings(hospital_id: int, settings: WhatsAppSettingsUpdate, admin: dict = Depends(get_current_admin)):
    HospitalService.update_whatsapp_settings(hospital_id, settings.model_dump(exclude_unset=True))
    return {"message": "WhatsApp settings updated"}

class SMTPConfigUpdate(BaseModel):
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_enabled: Optional[bool] = None
    smtp_use_ssl: Optional[bool] = None

@router.put("/{hospital_id}/smtp-settings")
def update_smtp_settings(hospital_id: int, smtp_config: SMTPConfigUpdate, admin: dict = Depends(get_current_admin)):
    HospitalService.update_smtp_settings(hospital_id, smtp_config.model_dump(exclude_unset=True))
    return {"message": "SMTP settings updated"}
