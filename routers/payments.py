from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from database import get_supabase
from models import PaymentStatus, PaymentMethod
# Note: Payment, Appointment, Operation, User, Hospital SQLAlchemy models removed - using Supabase now
from auth import get_current_user, get_current_doctor
from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, validator
import uuid
import json
import logging
import os

# Import Razorpay services
from services.razorpay_service import RazorpayService
from payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)

# Try to import QR code library
try:
    import qrcode
    import io
    import base64
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

router = APIRouter(prefix="/api/payments", tags=["payments"])

class PaymentCreate(BaseModel):
    appointment_id: Optional[int] = None
    operation_id: Optional[int] = None
    amount: str = "500"

class QRGenerateRequest(BaseModel):
    upi_id: str
    amount: str = "500"
    transaction_id: Optional[str] = None

def generate_upi_qr_code(upi_id: str, amount: str, transaction_id: str) -> str:
    """Generate UPI QR code as base64 string"""
    if not QR_AVAILABLE:
        # Return placeholder if QR library not available
        return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUwIiBoZWlnaHQ9IjI1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjUwIiBoZWlnaHQ9IjI1MCIgZmlsbD0iI2Y5ZmFmYiIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM2YjcyODAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj5VUEkgUVIgQ29kZTwvdGV4dD48L3N2Zz4="
    
    # UPI payment URL format
    upi_url = f"upi://pay?pa={upi_id}&am={amount}&tn=Appointment%20Payment&tr={transaction_id}"
    
    try:
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        # Return placeholder on error
        return "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjUwIiBoZWlnaHQ9IjI1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjUwIiBoZWlnaHQ9IjI1MCIgZmlsbD0iI2Y5ZmFmYiIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM2YjcyODAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj5VUEkgUVIgQ29kZTwvdGV4dD48L3N2Zz4="

@router.post("/create")
def create_payment(
    payment_data: PaymentCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a payment request and generate UPI QR codes - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    if not payment_data.appointment_id and not payment_data.operation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either appointment_id or operation_id is required"
        )
    
    # Get hospital
    hospital_id = None
    if payment_data.appointment_id:
        appointment_result = supabase.table("appointments").select("*").eq("id", payment_data.appointment_id).execute()
        if not appointment_result.data:
            raise HTTPException(status_code=404, detail="Appointment not found")
        appointment = appointment_result.data[0]
        if appointment["user_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        hospital_id = appointment.get("hospital_id") or current_user.get("hospital_id")
    elif payment_data.operation_id:
        operation_result = supabase.table("operations").select("*").eq("id", payment_data.operation_id).execute()
        if not operation_result.data:
            raise HTTPException(status_code=404, detail="Operation not found")
        operation = operation_result.data[0]
        if operation["patient_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized")
        hospital_id = operation.get("hospital_id") or current_user.get("hospital_id")
    
    if not hospital_id:
        raise HTTPException(status_code=400, detail="Hospital not found")
    
    hospital_result = supabase.table("hospitals").select("*").eq("id", hospital_id).execute()
    if not hospital_result.data:
        raise HTTPException(status_code=404, detail="Hospital not found")
    hospital = hospital_result.data[0]
    
    # Get UPI IDs for each payment app (use app-specific or fallback to default)
    gpay_upi = hospital.get("gpay_upi_id") or hospital.get("upi_id") or "hospital@upi"
    phonepay_upi = hospital.get("phonepay_upi_id") or hospital.get("upi_id") or "hospital@upi"
    paytm_upi = hospital.get("paytm_upi_id") or hospital.get("upi_id") or "hospital@upi"
    bhim_upi = hospital.get("bhim_upi_id") or hospital.get("upi_id") or "hospital@upi"
    default_upi = hospital.get("upi_id") or "hospital@upi"
    
    # Generate transaction ID
    transaction_id = f"TXN{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"
    
    # Create payment record
    payment_record = {
        "appointment_id": payment_data.appointment_id,
        "operation_id": payment_data.operation_id,
        "user_id": current_user["id"],
        "hospital_id": hospital_id,
        "amount": payment_data.amount,
        "status": "PENDING",
        "transaction_id": transaction_id,
        "payment_method": "upi"
    }
    
    result = supabase.table("payments").insert(payment_record).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment record"
        )
    payment = result.data[0]
    
    # Generate QR codes for each UPI app using their specific UPI IDs
    qr_codes = {
        "gpay": generate_upi_qr_code(gpay_upi, payment_data.amount, transaction_id),
        "phonepay": generate_upi_qr_code(phonepay_upi, payment_data.amount, transaction_id),
        "paytm": generate_upi_qr_code(paytm_upi, payment_data.amount, transaction_id),
        "bhimupi": generate_upi_qr_code(bhim_upi, payment_data.amount, transaction_id)
    }
    
    # Generate UPI payment URLs for each app
    upi_url = f"upi://pay?pa={default_upi}&am={payment_data.amount}&tn=Appointment%20Payment&tr={transaction_id}"
    
    # Generate payment links for each UPI app using their specific UPI IDs
    payment_links = {
        "gpay": f"tez://pay?pa={gpay_upi}&am={payment_data.amount}&tn=Appointment%20Payment&tr={transaction_id}",
        "phonepay": f"phonepe://pay?pa={phonepay_upi}&am={payment_data.amount}&tn=Appointment%20Payment&tr={transaction_id}",
        "paytm": f"paytmmp://pay?pa={paytm_upi}&am={payment_data.amount}&tn=Appointment%20Payment&tr={transaction_id}",
        "bhimupi": f"upi://pay?pa={bhim_upi}&am={payment_data.amount}&tn=Appointment%20Payment&tr={transaction_id}",
        "universal": upi_url
    }
    
    return {
        "payment_id": payment["id"],
        "transaction_id": transaction_id,
        "amount": payment_data.amount,
        "upi_id": default_upi,
        "upi_url": upi_url,
        "qr_codes": qr_codes,
        "payment_links": payment_links,
        "status": payment["status"]
    }

@router.post("/verify/{payment_id}")
def verify_payment(
    payment_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Verify payment status (manual verification) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    result = supabase.table("payments").select("*").eq("id", payment_id).eq("user_id", current_user["id"]).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = result.data[0]
    
    # In production, integrate with payment gateway webhook
    # For now, return current status
    return {
        "payment_id": payment["id"],
        "status": payment["status"],
        "transaction_id": payment.get("transaction_id") or payment.get("internal_transaction_id"),
        "amount": payment["amount"]
    }

@router.put("/complete/{payment_id}")
def complete_payment(
    payment_id: int,
    upi_transaction_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Mark payment as completed (admin/doctor function) - using Supabase"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    # Get payment
    payment_result = supabase.table("payments").select("*").eq("id", payment_id).execute()
    if not payment_result.data:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    payment = payment_result.data[0]
    
    # Update payment status
    update_data = {
        "status": "COMPLETED",
        "completed_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    if upi_transaction_id:
        update_data["upi_transaction_id"] = upi_transaction_id
    
    supabase.table("payments").update(update_data).eq("id", payment_id).execute()
    
    # Update appointment/operation status if payment completed
    if payment.get("appointment_id"):
        supabase.table("appointments").update({"status": "confirmed"}).eq("id", payment["appointment_id"]).execute()
    elif payment.get("operation_id"):
        supabase.table("operations").update({"status": "confirmed"}).eq("id", payment["operation_id"]).execute()
    
    # Get updated payment
    updated_payment = supabase.table("payments").select("*").eq("id", payment_id).execute()
    
    return {"message": "Payment marked as completed", "payment": updated_payment.data[0] if updated_payment.data else payment}

@router.get("/my-payments")
def get_my_payments(
    current_user: dict = Depends(get_current_user)
):
    """Get all payments for current user"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("payments").select("*").eq(
            "user_id", current_user["id"]
        ).order("created_at", desc=True).execute()
        
        payments = []
        for p in (result.data or []):
            payments.append({
                "id": p["id"],
                "appointment_id": p.get("appointment_id"),
                "operation_id": p.get("operation_id"),
                "amount": p.get("amount"),
                "currency": p.get("currency", "INR"),
                "status": p.get("status"),
                "payment_method": p.get("payment_method"),
                "razorpay_order_id": p.get("razorpay_order_id"),
                "razorpay_payment_id": p.get("razorpay_payment_id"),
                "transaction_id": p.get("transaction_id") or p.get("internal_transaction_id"),
                "payment_date": p.get("payment_date") or p.get("completed_at"),
                "created_at": p.get("created_at"),
                "completed_at": p.get("completed_at"),
                "failed_at": p.get("failed_at"),
                "failure_reason": p.get("failure_reason")
            })
        
        return payments
    except Exception as e:
        logger.error(f"Error fetching payments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payments: {str(e)}"
        )

class QRGenerateRequest(BaseModel):
    upi_id: str
    amount: str = "500"
    transaction_id: Optional[str] = None

@router.post("/generate-qr")
def generate_qr_code(request: QRGenerateRequest):
    """Generate QR code for homepage (public endpoint)"""
    from datetime import datetime
    if not request.transaction_id:
        request.transaction_id = f"HOME{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    qr_code = generate_upi_qr_code(request.upi_id, request.amount, request.transaction_id)
    return {
        "qr_code": qr_code,
        "upi_id": request.upi_id,
        "amount": request.amount
    }

# ============================================
# Razorpay Payment Endpoints
# ============================================

class RazorpayOrderCreate(BaseModel):
    appointment_id: Optional[int] = None
    operation_id: Optional[int] = None
    hospital_registration: Optional[bool] = False  # For hospital registration payments
    plan_name: Optional[str] = None  # Package/plan name
    amount: float  # Will accept int and convert to float
    currency: str = "INR"
    
    @validator('amount', pre=True)
    def convert_amount_to_float(cls, v):
        """Convert amount to float for consistency (handles int from mobile app)"""
        if v is None:
            raise ValueError("Amount is required")
        try:
            return float(v)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid amount: {v}. Must be a number.")

@router.post("/create-order-hospital")
def create_hospital_registration_order(
    order_data: RazorpayOrderCreate
):
    """
    Create Razorpay order for hospital registration or package purchase
    Razorpay order is created FIRST, DB insert happens only after success
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )

    # Validation
    if not order_data.hospital_registration and not order_data.plan_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either hospital_registration or plan_name is required"
        )

    if order_data.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amount must be greater than 0"
        )

    try:
        import time
        import hashlib

        # -----------------------------
        # Generate INTERNAL transaction ID (long – for DB)
        # -----------------------------
        timestamp = int(time.time())
        prefix = "HOSPREG" if order_data.hospital_registration else "PKG"
        raw_key = f"{prefix}_{order_data.plan_name}_{timestamp}"
        hash_part = hashlib.md5(raw_key.encode()).hexdigest()[:8]

        internal_transaction_id = f"{prefix}_{timestamp}_{hash_part}"

        # -----------------------------
        # Idempotency check
        # -----------------------------
        existing = supabase.table("payments").select("*").eq(
            "internal_transaction_id", internal_transaction_id
        ).execute()

        if existing.data:
            payment = existing.data[0]
            if payment.get("razorpay_order_id"):
                return {
                    "payment_id": payment["id"],
                    "order_id": payment["razorpay_order_id"],
                    "amount": float(payment["amount"]),
                    "currency": payment.get("currency", "INR"),
                    "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
                    "status": payment["status"],
                }

        # -----------------------------
        # Razorpay receipt (SHORT ≤ 40 chars)
        # -----------------------------
        receipt = f"RCPT_{timestamp}"

        # -----------------------------
        # Notes (LONG data goes here)
        # -----------------------------
        notes = {
            "type": "hospital_registration" if order_data.hospital_registration else "package_purchase",
            "plan_name": order_data.plan_name,
            "internal_transaction_id": internal_transaction_id
        }

        # -----------------------------
        # Create Razorpay order (FIRST)
        # -----------------------------
        order = PaymentGateway.create_order(
            amount=order_data.amount,
            currency=order_data.currency,
            receipt=receipt,
            notes=notes
        )

        if not order or not order.get("order_id"):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Razorpay order creation failed"
            )

        # -----------------------------
        # Create payment record (ONLY AFTER Razorpay success)
        # -----------------------------
        payment_record = {
            "user_id": None,
            "hospital_id": None,
            "amount": str(order_data.amount),
            "currency": order_data.currency,
            "payment_method": "razorpay",
            "status": "PENDING",
            "razorpay_order_id": order["order_id"],
            "internal_transaction_id": internal_transaction_id,
            "initiated_at": datetime.now().isoformat(),
            "metadata": {
                "type": notes["type"],
                "plan_name": order_data.plan_name,
                "total_amount": order_data.amount
            }
        }

        result = supabase.table("payments").insert(payment_record).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save payment record"
            )

        payment = result.data[0]

        return {
            "payment_id": payment["id"],
            "order_id": order["order_id"],
            "amount": float(order_data.amount),  # Ensure float type for mobile app compatibility
            "currency": order_data.currency,
            "key_id": order.get("key_id", os.getenv("RAZORPAY_KEY_ID", "")),
            "status": payment["status"],
            "internal_transaction_id": internal_transaction_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hospital order creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment order"
        )

@router.post("/create-order")
def create_razorpay_order(
    order_data: RazorpayOrderCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Create Razorpay order and payment record
    Returns order details for frontend Razorpay Checkout
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Validate request
        if not order_data.appointment_id and not order_data.operation_id and not order_data.hospital_registration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either appointment_id, operation_id, or hospital_registration is required"
            )
        
        if order_data.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be greater than 0"
            )
        
        # Get hospital_id from appointment or operation
        hospital_id = None
        if order_data.appointment_id:
            appointment_result = supabase.table("appointments").select("*").eq(
                "id", order_data.appointment_id
            ).execute()
            if not appointment_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Appointment not found"
                )
            appointment = appointment_result.data[0]
            if appointment["user_id"] != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create payment for this appointment"
                )
            hospital_id = appointment.get("hospital_id")
        else:
            operation_result = supabase.table("operations").select("*").eq(
                "id", order_data.operation_id
            ).execute()
            if not operation_result.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Operation not found"
                )
            operation = operation_result.data[0]
            if operation["patient_id"] != current_user["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create payment for this operation"
                )
            hospital_id = operation.get("hospital_id")
        
        if not hospital_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hospital not found for this appointment/operation"
            )
        
        # Check idempotency - look for existing payment with same reference
        internal_transaction_id = RazorpayService.generate_idempotency_key(
            current_user["id"], order_data.appointment_id, order_data.operation_id
        )
        
        existing_payment = supabase.table("payments").select("*").eq(
            "internal_transaction_id", internal_transaction_id
        ).execute()
        
        if existing_payment.data:
            # Return existing payment
            payment = existing_payment.data[0]
            if payment.get("razorpay_order_id"):
                return {
                    "payment_id": payment["id"],
                    "order_id": payment["razorpay_order_id"],
                    "amount": float(payment["amount"]),
                    "currency": payment.get("currency", "INR"),
                    "key_id": os.getenv("RAZORPAY_KEY_ID", ""),
                    "status": payment["status"]
                }
        
        # Create Razorpay order
        order_result = RazorpayService.create_razorpay_order(
            amount=order_data.amount,
            currency=order_data.currency,
            user_id=current_user["id"],
            appointment_id=order_data.appointment_id,
            operation_id=order_data.operation_id,
            hospital_id=hospital_id
        )
        
        if not order_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create Razorpay order"
            )
        
        # Create payment record
        payment_record = {
            "appointment_id": order_data.appointment_id,
            "operation_id": order_data.operation_id,
            "user_id": current_user["id"],
            "hospital_id": hospital_id,
            "amount": str(order_data.amount),
            "currency": order_data.currency,
            "payment_method": "razorpay",
            "status": "PENDING",
            "razorpay_order_id": order_result.get("order_id"),
            "internal_transaction_id": internal_transaction_id,
            "initiated_at": datetime.now().isoformat()
        }
        
        result = supabase.table("payments").insert(payment_record).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create payment record"
            )
        
        payment = result.data[0]
        
        return {
            "payment_id": payment["id"],
            "order_id": order_result.get("order_id"),
            "amount": float(order_data.amount),  # Ensure float type for mobile app compatibility
            "currency": order_data.currency,
            "key_id": order_result.get("key_id", os.getenv("RAZORPAY_KEY_ID", "")),
            "status": payment["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating order: {str(e)}"
        )

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature")
):
    """
    Razorpay webhook endpoint
    Handles payment.captured, payment.failed, and other events
    """
    supabase = get_supabase()
    if not supabase:
        logger.error("Database not configured for webhook")
        return {"status": "error", "message": "Database not configured"}
    
    try:
        # Get raw payload for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        webhook_payload = json.loads(body_str)
        
        # Verify webhook signature
        if not x_razorpay_signature:
            logger.error("Missing X-Razorpay-Signature header")
            return {"status": "error", "message": "Missing signature"}
        
        if not PaymentGateway.verify_webhook_signature(body_str, x_razorpay_signature):
            logger.error("Invalid webhook signature")
            return {"status": "error", "message": "Invalid signature"}
        
        # Process webhook event
        process_result = RazorpayService.process_webhook_event(
            webhook_payload, x_razorpay_signature
        )
        
        if not process_result.get("success"):
            logger.error(f"Webhook processing failed: {process_result.get('error')}")
            return {"status": "error", "message": process_result.get("error")}
        
        webhook_id = process_result.get("webhook_id")
        event_type = process_result.get("event_type")
        razorpay_payment_id = process_result.get("razorpay_payment_id")
        razorpay_order_id = process_result.get("razorpay_order_id")
        payment_entity = process_result.get("payment_entity")
        
        # Check idempotency
        if RazorpayService.check_webhook_idempotency(webhook_id):
            logger.info(f"Webhook {webhook_id} already processed, skipping")
            return {"status": "success", "message": "Already processed"}
        
        # Save webhook event
        webhook_record_id = RazorpayService.save_webhook_event(
            webhook_id=webhook_id,
            event_type=event_type,
            payment_id=None,  # Will be set after finding payment
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            webhook_payload=webhook_payload,
            signature_verified=True
        )
        
        if not webhook_record_id:
            logger.error("Failed to save webhook event")
            return {"status": "error", "message": "Failed to save webhook"}
        
        # Find payment by razorpay_order_id
        payment_result = supabase.table("payments").select("*").eq(
            "razorpay_order_id", razorpay_order_id
        ).execute()
        
        if not payment_result.data:
            logger.error(f"Payment not found for order_id: {razorpay_order_id}")
            RazorpayService.mark_webhook_processed(
                webhook_id, error=f"Payment not found for order {razorpay_order_id}"
            )
            return {"status": "error", "message": "Payment not found"}
        
        payment = payment_result.data[0]
        payment_id = payment["id"]
        
        # Verify payment from Razorpay API (backend-owned verification)
        razorpay_payment = RazorpayService.verify_payment_from_razorpay(razorpay_payment_id)
        
        if not razorpay_payment:
            logger.error(f"Could not fetch payment from Razorpay: {razorpay_payment_id}")
            RazorpayService.mark_webhook_processed(
                webhook_id, payment_id=payment_id,
                error="Could not fetch payment from Razorpay"
            )
            return {"status": "error", "message": "Payment verification failed"}
        
        # Cross-verify: Compare webhook data with Razorpay API response
        if (razorpay_payment.get("order_id") != razorpay_order_id or
            float(razorpay_payment.get("amount", 0)) / 100 != float(payment.get("amount", 0))):
            logger.error("Payment verification mismatch")
            RazorpayService.mark_webhook_processed(
                webhook_id, payment_id=payment_id,
                error="Payment verification mismatch"
            )
            return {"status": "error", "message": "Payment verification mismatch"}
        
        # Process based on event type
        if event_type == "payment.captured":
            # Update payment status to COMPLETED
            update_data = {
                "status": "COMPLETED",
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": x_razorpay_signature,
                "gateway_transaction_id": razorpay_payment.get("id"),
                "completed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            supabase.table("payments").update(update_data).eq("id", payment_id).execute()
            
            # Update appointment/operation status
            if payment.get("appointment_id"):
                supabase.table("appointments").update({
                    "status": "confirmed"
                }).eq("id", payment["appointment_id"]).execute()
            elif payment.get("operation_id"):
                supabase.table("operations").update({
                    "status": "confirmed"
                }).eq("id", payment["operation_id"]).execute()
            
            # Mark webhook as processed
            RazorpayService.mark_webhook_processed(webhook_id, payment_id=payment_id)
            
            logger.info(f"Payment {payment_id} marked as COMPLETED via webhook {webhook_id}")
            
        elif event_type == "payment.failed":
            # Update payment status to FAILED
            failure_reason = payment_entity.get("error_description") or payment_entity.get("error_code", "Unknown error")
            update_data = {
                "status": "FAILED",
                "razorpay_payment_id": razorpay_payment_id,
                "failure_reason": failure_reason,
                "failure_code": payment_entity.get("error_code"),
                "failed_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            supabase.table("payments").update(update_data).eq("id", payment_id).execute()
            
            # Mark webhook as processed
            RazorpayService.mark_webhook_processed(webhook_id, payment_id=payment_id)
            
            logger.info(f"Payment {payment_id} marked as FAILED via webhook {webhook_id}")
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/{payment_id}")
def get_payment(
    payment_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get payment details"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("payments").select("*").eq("id", payment_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment = result.data[0]
        
        # Check authorization
        if payment["user_id"] != current_user["id"]:
            # Allow doctors to view payments for their hospital
            if current_user.get("role") == "doctor":
                if payment.get("hospital_id") != current_user.get("hospital_id"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not authorized"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized"
                )
        
        return payment
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment: {str(e)}"
        )

@router.get("/{payment_id}/status")
def get_payment_status(
    payment_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get payment status (for polling)"""
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        result = supabase.table("payments").select("id, status, razorpay_payment_id, completed_at").eq(
            "id", payment_id
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment = result.data[0]
        
        # Check authorization
        if payment.get("user_id") != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        return {
            "payment_id": payment["id"],
            "status": payment["status"],
            "razorpay_payment_id": payment.get("razorpay_payment_id"),
            "completed_at": payment.get("completed_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payment status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment status: {str(e)}"
        )

@router.post("/{payment_id}/verify")
def verify_payment_manually(
    payment_id: int,
    current_doctor: dict = Depends(get_current_doctor)
):
    """
    Manually verify payment (admin/doctor function)
    Fetches payment status from Razorpay and updates database
    """
    supabase = get_supabase()
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Get payment
        result = supabase.table("payments").select("*").eq("id", payment_id).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        payment = result.data[0]
        
        if not payment.get("razorpay_payment_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment does not have Razorpay payment ID"
            )
        
        # Fetch from Razorpay
        razorpay_payment = RazorpayService.verify_payment_from_razorpay(
            payment["razorpay_payment_id"]
        )
        
        if not razorpay_payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found in Razorpay"
            )
        
        # Update payment status based on Razorpay status
        razorpay_status = razorpay_payment.get("status")
        new_status = None
        
        if razorpay_status == "captured":
            new_status = "COMPLETED"
        elif razorpay_status == "failed":
            new_status = "FAILED"
        elif razorpay_status == "authorized":
            new_status = "PENDING"
        
        if new_status:
            update_data = {
                "status": new_status,
                "updated_at": datetime.now().isoformat()
            }
            
            if new_status == "COMPLETED":
                update_data["completed_at"] = datetime.now().isoformat()
            elif new_status == "FAILED":
                update_data["failed_at"] = datetime.now().isoformat()
                update_data["failure_reason"] = razorpay_payment.get("error_description")
            
            supabase.table("payments").update(update_data).eq("id", payment_id).execute()
        
        return {
            "verified": True,
            "status": new_status or payment["status"],
            "razorpay_status": razorpay_status,
            "details": {
                "amount": razorpay_payment.get("amount", 0) / 100,
                "currency": razorpay_payment.get("currency"),
                "method": razorpay_payment.get("method")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying payment: {str(e)}"
        )
