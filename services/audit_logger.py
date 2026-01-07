"""
Audit Logging Service for Legal Compliance
Logs all critical actions for legal safety and compliance
"""
from datetime import datetime
from typing import Optional, Dict, Any
from database import get_supabase


def log_audit_event(
    event_type: str,
    user_id: Optional[int] = None,
    user_role: Optional[str] = None,
    action: str = "",
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None
):
    """
    Log audit event to database
    
    Event Types:
    - login_attempt: Login attempts (success/failure)
    - logout: User logout
    - appointment_create: Appointment creation
    - appointment_update: Appointment changes (status, cancellation)
    - appointment_delete: Appointment deletion
    - operation_create: Operation creation
    - operation_update: Operation changes
    - operation_delete: Operation deletion
    - payment_create: Payment creation
    - payment_update: Payment status changes
    - data_export: Data export/download
    - message_send: WhatsApp/Email message sending
    - user_create: User registration
    - user_update: User profile updates
    - hospital_create: Hospital registration
    - hospital_update: Hospital updates
    - hospital_approve: Hospital approval/rejection
    - pricing_update: Pricing configuration changes
    - admin_action: Admin-only actions
    """
    try:
        supabase = get_supabase()
        if not supabase:
            # Fallback to console logging if Supabase not available
            print(f"[AUDIT] {event_type}: {action} by user {user_id} - {status}")
            return
        
        audit_data = {
            "event_type": event_type,
            "user_id": user_id,
            "user_role": user_role,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,  # Supabase handles JSONB as dict directly
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status": status,
            "error_message": error_message,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Insert into audit_logs table
        result = supabase.table("audit_logs").insert(audit_data).execute()
        
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        # Never fail the main operation due to audit logging issues
        print(f"[AUDIT ERROR] Failed to log event {event_type}: {str(e)}")
        return None


def log_login_attempt(
    mobile: str,
    user_id: Optional[int] = None,
    success: bool = True,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    error_message: Optional[str] = None
):
    """Log login attempt"""
    return log_audit_event(
        event_type="login_attempt",
        user_id=user_id,
        action=f"Login attempt: {mobile}",
        details={"mobile": mobile, "success": success},
        ip_address=ip_address,
        user_agent=user_agent,
        status="success" if success else "failed",
        error_message=error_message
    )


def log_appointment_change(
    appointment_id: int,
    user_id: int,
    user_role: str,
    action: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log appointment changes"""
    action_details = details or {}
    if old_status and new_status:
        action_details["status_change"] = f"{old_status} -> {new_status}"
    
    return log_audit_event(
        event_type="appointment_update" if "update" in action.lower() else "appointment_create",
        user_id=user_id,
        user_role=user_role,
        action=action,
        resource_type="appointment",
        resource_id=appointment_id,
        details=action_details,
        ip_address=ip_address
    )


def log_operation_change(
    operation_id: int,
    user_id: int,
    user_role: str,
    action: str,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log operation changes"""
    action_details = details or {}
    if old_status and new_status:
        action_details["status_change"] = f"{old_status} -> {new_status}"
    
    return log_audit_event(
        event_type="operation_update" if "update" in action.lower() else "operation_create",
        user_id=user_id,
        user_role=user_role,
        action=action,
        resource_type="operation",
        resource_id=operation_id,
        details=action_details,
        ip_address=ip_address
    )


def log_data_export(
    user_id: int,
    user_role: str,
    export_type: str,
    record_count: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log data export/download"""
    export_details = details or {}
    export_details["export_type"] = export_type
    if record_count is not None:
        export_details["record_count"] = record_count
    
    return log_audit_event(
        event_type="data_export",
        user_id=user_id,
        user_role=user_role,
        action=f"Data export: {export_type}",
        resource_type=export_type,
        details=export_details,
        ip_address=ip_address
    )


def log_message_send(
    user_id: Optional[int],
    message_type: str,  # whatsapp, email
    recipient: str,
    subject_or_purpose: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log message sending (WhatsApp/Email)"""
    message_details = details or {}
    message_details["recipient"] = recipient
    message_details["message_type"] = message_type
    if subject_or_purpose:
        message_details["subject"] = subject_or_purpose
    
    return log_audit_event(
        event_type="message_send",
        user_id=user_id,
        action=f"Send {message_type} to {recipient}",
        details=message_details,
        status="success" if success else "failed",
        error_message=error_message
    )


def log_payment_event(
    payment_id: int,
    user_id: int,
    action: str,
    amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log payment events"""
    payment_details = details or {}
    if amount:
        payment_details["amount"] = amount
    if payment_method:
        payment_details["payment_method"] = payment_method
    
    return log_audit_event(
        event_type="payment_create" if "create" in action.lower() else "payment_update",
        user_id=user_id,
        action=action,
        resource_type="payment",
        resource_id=payment_id,
        details=payment_details,
        ip_address=ip_address,
        status=status
    )


def get_audit_logs(
    user_id: Optional[int] = None,
    event_type: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
):
    """Retrieve audit logs with filtering"""
    try:
        supabase = get_supabase()
        if not supabase:
            return []
        
        query = supabase.table("audit_logs").select("*")
        
        if user_id:
            query = query.eq("user_id", user_id)
        if event_type:
            query = query.eq("event_type", event_type)
        if resource_type:
            query = query.eq("resource_type", resource_type)
        if resource_id:
            query = query.eq("resource_id", resource_id)
        if start_date:
            query = query.gte("created_at", start_date)
        if end_date:
            query = query.lte("created_at", end_date)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to retrieve logs: {str(e)}")
        return []

