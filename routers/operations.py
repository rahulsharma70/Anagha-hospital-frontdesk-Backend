from fastapi import APIRouter, Depends, HTTPException, status
from datetime import date, datetime
from database import get_supabase
from schemas import OperationCreate, OperationResponse
from auth import get_current_user, get_current_doctor
from typing import List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operations", tags=["operations"])

@router.post("/book", response_model=dict)
def book_operation(
    operation: OperationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Book an operation (for patients and pharma professionals) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check if date is in the past
        if operation.date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book operation for past dates"
            )
        
        # Verify doctor exists and is a doctor
        doctor_result = supabase.table("users").select("*").eq("id", operation.doctor_id).eq("role", "doctor").eq("is_active", True).execute()
        if not doctor_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )
        doctor = doctor_result.data[0]
        
        # Validate doctor-hospital relationship
        doctor_hospital_id = doctor.get("hospital_id")
        user_hospital_id = current_user.get("hospital_id")
        
        # Doctor must have a hospital_id
        if not doctor_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is not associated with any hospital"
            )
        
        # If user has hospital_id, it must match doctor's hospital_id
        if user_hospital_id and user_hospital_id != doctor_hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor does not belong to your selected hospital"
            )
        
        # Use doctor's hospital_id (required)
        hospital_id = doctor_hospital_id
        
        # Verify hospital exists and is approved
        hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
        if not hospital_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hospital not found"
            )
        hospital = hospital_result.data[0]
        
        # Ensure hospital is approved
        if hospital.get("status") != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book operation with unapproved hospital"
            )
        
        # Create operation record with mandatory hospital_id
        operation_record = {
            "patient_id": current_user["id"],
            "specialty": operation.specialty.value if hasattr(operation.specialty, 'value') else str(operation.specialty),
            "operation_date": str(operation.date),
            "doctor_id": operation.doctor_id,
            "hospital_id": hospital_id,  # Mandatory hospital_id
            "status": "pending",
            "notes": operation.notes
        }
        
        result = supabase.table("operations").insert(operation_record).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create operation"
            )
        
        db_operation = result.data[0]
        
        # Verify hospital_id was persisted
        if not db_operation.get("hospital_id"):
            logger.error(f"Operation {db_operation.get('id')} created without hospital_id despite validation")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Operation created but hospital_id was not persisted. Please contact support."
            )
        
        # Return response with patient and doctor names
        return {
            "id": db_operation["id"],
            "patient_id": db_operation["patient_id"],
            "specialty": db_operation["specialty"],
            "date": db_operation.get("operation_date", db_operation.get("date", "")),
            "doctor_id": db_operation["doctor_id"],
            "hospital_id": db_operation.get("hospital_id", hospital_id),  # Include mandatory hospital_id
            "status": db_operation["status"],
            "created_at": db_operation.get("created_at", datetime.now().isoformat()),
            "notes": db_operation.get("notes"),
            "patient_name": current_user.get("name", ""),
            "doctor_name": doctor.get("name", ""),
            "hospital_name": hospital.get("name", "")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error booking operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error booking operation: {str(e)}"
        )

@router.get("/my-operations", response_model=List[dict])
def get_my_operations(current_user: dict = Depends(get_current_user)):
    """Get all operations for current user - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("operations").select("*").eq("patient_id", current_user["id"]).order("operation_date", desc=False).execute()
        
        operations = []
        for op in (result.data or []):
            # Fetch doctor info
            doctor_info = {}
            if op.get("doctor_id"):
                doctor_result = supabase.table("users").select("id, name, mobile").eq("id", op["doctor_id"]).execute()
                if doctor_result.data:
                    doctor_info = doctor_result.data[0]
            
            # Fetch hospital info
            hospital_info = {}
            hospital_id = op.get("hospital_id")
            if hospital_id:
                hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
                if hospital_result.data:
                    hospital_info = hospital_result.data[0]
            
            operations.append({
                "id": op["id"],
                "patient_id": op["patient_id"],
                "specialty": op["specialty"],
                "date": op.get("operation_date", op.get("date", "")),
                "doctor_id": op["doctor_id"],
                "hospital_id": hospital_id,  # Include persisted hospital_id
                "status": op["status"],
                "created_at": op.get("created_at", ""),
                "notes": op.get("notes"),
                "patient_name": current_user.get("name", ""),
                "doctor_name": doctor_info.get("name", "Unknown"),
                "hospital_name": hospital_info.get("name", "Unknown Hospital")
            })
        
        return operations
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching operations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching operations: {str(e)}"
        )

@router.get("/doctor-operations", response_model=List[dict])
def get_doctor_operations(current_doctor: dict = Depends(get_current_doctor)):
    """Get all operations for current doctor - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        result = supabase.table("operations").select("*").eq("doctor_id", current_doctor["id"]).order("operation_date", desc=False).execute()
        
        operations = []
        for op in (result.data or []):
            # Fetch patient info
            patient_info = {}
            if op.get("patient_id"):
                patient_result = supabase.table("users").select("id, name, mobile").eq("id", op["patient_id"]).execute()
                if patient_result.data:
                    patient_info = patient_result.data[0]
            
            # Fetch hospital info
            hospital_info = {}
            hospital_id = op.get("hospital_id")
            if hospital_id:
                hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
                if hospital_result.data:
                    hospital_info = hospital_result.data[0]
            
            operations.append({
                "id": op["id"],
                "patient_id": op["patient_id"],
                "specialty": op["specialty"],
                "date": op.get("operation_date", op.get("date", "")),
                "doctor_id": op["doctor_id"],
                "hospital_id": hospital_id,  # Include persisted hospital_id
                "status": op["status"],
                "created_at": op.get("created_at", ""),
                "notes": op.get("notes"),
                "patient_name": patient_info.get("name", "Unknown"),
                "doctor_name": current_doctor.get("name", ""),
                "hospital_name": hospital_info.get("name", "Unknown Hospital")
            })
        
        return operations
    except Exception as e:
        logger.error(f"Error fetching doctor operations: {e}")
        return []

@router.put("/{operation_id}/confirm")
def confirm_operation(
    operation_id: int,
    current_doctor: dict = Depends(get_current_doctor)
):
    """Confirm an operation (doctor only) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check operation exists and belongs to doctor
        operation_result = supabase.table("operations").select("*").eq(
            "id", operation_id
        ).eq("doctor_id", current_doctor["id"]).execute()
        
        if not operation_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Operation not found"
            )
        
        # Update status
        update_result = supabase.table("operations").update({
            "status": "confirmed"
        }).eq("id", operation_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to confirm operation"
            )
        
        return {"message": "Operation confirmed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error confirming operation: {str(e)}"
        )

@router.put("/{operation_id}/cancel")
def cancel_operation(
    operation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Cancel an operation - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Check operation exists
        operation_result = supabase.table("operations").select("*").eq("id", operation_id).execute()
        
        if not operation_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Operation not found"
            )
        
        operation = operation_result.data[0]
        
        # Only allow cancellation by the patient or the doctor
        if operation["patient_id"] != current_user["id"] and operation["doctor_id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to cancel this operation"
            )
        
        # Update status
        update_result = supabase.table("operations").update({
            "status": "cancelled"
        }).eq("id", operation_id).execute()
        
        if not update_result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel operation"
            )
        
        return {"message": "Operation cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling operation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling operation: {str(e)}"
        )

@router.get("/by-specialty/{specialty}")
def get_operations_by_specialty(
    specialty: str,
    current_user: dict = Depends(get_current_user)
):
    """Get operations filtered by specialty - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        return []
    
    try:
        if current_user.get("role") == "doctor":
            result = supabase.table("operations").select("*").eq(
                "specialty", specialty
            ).eq("doctor_id", current_user["id"]).order("operation_date", desc=False).execute()
        else:
            result = supabase.table("operations").select("*").eq(
                "specialty", specialty
            ).eq("patient_id", current_user["id"]).order("operation_date", desc=False).execute()
        
        operations = []
        for op in (result.data or []):
            # Fetch patient info
            patient_info = {}
            if op.get("patient_id"):
                patient_result = supabase.table("users").select("id, name, mobile").eq("id", op["patient_id"]).execute()
                if patient_result.data:
                    patient_info = patient_result.data[0]
            
            # Fetch doctor info
            doctor_info = {}
            if op.get("doctor_id"):
                doctor_result = supabase.table("users").select("id, name, mobile").eq("id", op["doctor_id"]).execute()
                if doctor_result.data:
                    doctor_info = doctor_result.data[0]
            
            # Fetch hospital info
            hospital_info = {}
            hospital_id = op.get("hospital_id")
            if hospital_id:
                hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
                if hospital_result.data:
                    hospital_info = hospital_result.data[0]
            
            operations.append({
                "id": op["id"],
                "patient_id": op["patient_id"],
                "specialty": op["specialty"],
                "date": op.get("operation_date", op.get("date", "")),
                "doctor_id": op["doctor_id"],
                "hospital_id": hospital_id,  # Include persisted hospital_id
                "status": op["status"],
                "created_at": op.get("created_at", ""),
                "notes": op.get("notes"),
                "patient_name": patient_info.get("name", "Unknown"),
                "doctor_name": doctor_info.get("name", "Unknown"),
                "hospital_name": hospital_info.get("name", "Unknown Hospital")
            })
        
        return operations
    except Exception as e:
        logger.error(f"Error fetching operations by specialty: {e}")
        return []
