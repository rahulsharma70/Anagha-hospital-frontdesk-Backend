from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from schemas import OperationCreate
from dependencies.auth import get_current_user, get_current_doctor
from services.operation_service import OperationService
from typing import List
from datetime import datetime
import logging
from services.whatsapp_service import send_whatsapp_message_by_hospital_id
from services.message_templates import get_confirmation_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/operations", tags=["operations"])

@router.post("/book", response_model=dict)
def book_operation(operation: OperationCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    result = OperationService.process_booking(operation.model_dump(), current_user)
    
    op = result["operation"]
    hospital = result["hospital"]
    
    if background_tasks and (hospital.get("whatsapp_enabled") == "true" or hospital.get("whatsapp_enabled") is True):
        msg = get_confirmation_message(
            patient_name=current_user.get("name", ""),
            doctor_name=result["doctor"].get("name", ""),
            date=str(operation.date),
            time_slot=None,
            hospital_name=hospital.get("name", ""),
            specialty=str(operation.specialty),
            custom_template=hospital.get("whatsapp_confirmation_template")
        )
        background_tasks.add_task(
            send_whatsapp_message_by_hospital_id,
            hospital_id=hospital["id"],
            mobile=current_user.get("mobile", ""),
            message=msg
        )

    return {
        "id": op["id"],
        "patient_id": op["patient_id"],
        "specialty": op["specialty"],
        "date": op.get("operation_date"),
        "doctor_id": op["doctor_id"],
        "hospital_id": op["hospital_id"],
        "status": op["status"],
        "created_at": op.get("created_at"),
        "notes": op.get("notes"),
        "patient_name": current_user.get("name", ""),
        "doctor_name": result["doctor"].get("name", ""),
        "hospital_name": hospital.get("name", "")
    }

@router.get("/my-operations", response_model=List[dict])
def get_my_operations(current_user: dict = Depends(get_current_user)):
    return OperationService.get_patient_operations(current_user["id"])

@router.get("/doctor-operations", response_model=List[dict])
def get_doctor_operations(current_doctor: dict = Depends(get_current_doctor)):
    return OperationService.get_doctor_operations(current_doctor["id"])

@router.put("/{operation_id}/confirm")
def confirm_operation(operation_id: int, current_doctor: dict = Depends(get_current_doctor)):
    OperationService.update_status(operation_id, current_doctor["id"], "confirm")
    return {"message": "Operation confirmed"}

@router.put("/{operation_id}/cancel")
def cancel_operation(operation_id: int, current_user: dict = Depends(get_current_user)):
    OperationService.update_status(operation_id, current_user["id"], "cancel")
    return {"message": "Operation cancelled"}

@router.get("/by-specialty/{specialty}")
def get_operations_by_specialty(specialty: str, current_user: dict = Depends(get_current_user)):
    is_doctor = current_user.get("role") == "doctor"
    return OperationService.get_operations_by_specialty(specialty, current_user["id"], is_doctor)
