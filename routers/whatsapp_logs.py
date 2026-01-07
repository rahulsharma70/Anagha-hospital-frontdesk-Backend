"""
WhatsApp Message Logs API
Provides endpoints to view message logs and statistics
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from database import get_supabase
# Note: Hospital SQLAlchemy model removed - using Supabase now
from services.message_logger import get_message_logs
from typing import Optional, List
from datetime import date

router = APIRouter(prefix="/api/whatsapp-logs", tags=["whatsapp-logs"])


@router.get("/{hospital_id}")
def get_hospital_message_logs(
    hospital_id: int,
    log_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format"),
    status_filter: Optional[str] = Query(None, description="Filter by status: 'success' or 'failed'")
):
    """
    Get WhatsApp message logs for a hospital.
    
    Features:
    - View all sent messages
    - Filter by date
    - Filter by status (success/failed)
    - View retry attempts
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Verify hospital exists
    hospital_result = supabase.table("hospitals").select("id, name").eq("id", hospital_id).execute()
    if not hospital_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    hospital = hospital_result.data[0]
    
    # Get logs
    logs = get_message_logs(hospital_id, date=log_date, status=status_filter)
    
    # Calculate statistics
    total = len(logs)
    successful = len([l for l in logs if l.get("status") == "success" or l.get("status") == "sent"])
    failed = len([l for l in logs if l.get("status") == "failed"])
    
    return {
        "hospital_id": hospital_id,
        "hospital_name": hospital.get("name", ""),
        "date": log_date or date.today().isoformat(),
        "statistics": {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round((successful / total * 100) if total > 0 else 0, 2)
        },
        "logs": logs
    }


@router.get("/{hospital_id}/failed")
def get_failed_messages(
    hospital_id: int,
    log_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format")
):
    """
    Get failed WhatsApp messages for a hospital.
    Useful for retry mechanism.
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Verify hospital exists
    hospital_result = supabase.table("hospitals").select("id").eq("id", hospital_id).execute()
    if not hospital_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hospital not found"
        )
    
    failed_logs = get_message_logs(hospital_id, date=log_date, status="failed")
    
    return {
        "hospital_id": hospital_id,
        "failed_count": len(failed_logs),
        "failed_messages": failed_logs
    }



