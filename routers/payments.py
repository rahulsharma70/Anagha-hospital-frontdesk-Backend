"""
Payments Router
Gateway-agnostic — works with Razorpay, Cashfree, or any future gateway.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from dependencies.auth import get_current_user
from services.payment_service import PaymentService
from services.gateways import get_payment_gateway
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


# ── Request Models ──────────────────────────────────────────

class OrderCreate(BaseModel):
    appointment_id: Optional[int] = None
    operation_id: Optional[int] = None
    amount: float
    currency: str = "INR"


class HospitalOrderCreate(BaseModel):
    hospital_registration: bool = True
    plan_name: str
    amount: float
    currency: str = "INR"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None


class GuestOrderCreate(BaseModel):
    appointment_id: Optional[int] = None
    operation_id: Optional[int] = None
    amount: float
    currency: str = "INR"


# ── Endpoints ───────────────────────────────────────────────

@router.post("/create-order")
def create_payment_order(order_data: OrderCreate, current_user: dict = Depends(get_current_user)):
    """Create a payment order for an authenticated user."""
    if not order_data.appointment_id and not order_data.operation_id:
        raise HTTPException(status_code=400, detail="Booking ID required")

    booking_id = order_data.appointment_id or order_data.operation_id
    b_type = "appointment" if order_data.appointment_id else "operation"

    return PaymentService.create_order(
        booking_id=booking_id,
        booking_type=b_type,
        amount=order_data.amount,
        user_id=current_user["id"],
    )


@router.post("/create-order-guest")
def create_guest_order(order_data: GuestOrderCreate):
    """Create a payment order for a guest (no auth required)."""
    if not order_data.appointment_id and not order_data.operation_id:
        raise HTTPException(status_code=400, detail="Booking ID required")

    booking_id = order_data.appointment_id or order_data.operation_id
    b_type = "appointment" if order_data.appointment_id else "operation"

    return PaymentService.create_order(
        booking_id=booking_id,
        booking_type=b_type,
        amount=order_data.amount,
        user_id=None,
    )


@router.post("/create-order-hospital")
def create_hospital_order(order_data: HospitalOrderCreate):
    """Create a payment order for hospital plan registration (no auth required)."""
    return PaymentService.create_hospital_order(
        plan_name=order_data.plan_name,
        amount=order_data.amount,
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        customer_email=order_data.customer_email,
    )


@router.post("/webhook")
async def payment_webhook_receiver(request: Request):
    """
    Gateway-agnostic webhook handler.
    Reads the correct signature header based on the active gateway.
    """
    raw_body = await request.body()
    gateway = get_payment_gateway()

    # Extract signature from the right header
    if gateway.name == "razorpay":
        signature = request.headers.get("x-razorpay-signature", "")
    else:  # cashfree
        signature = request.headers.get("x-webhook-signature", "")

    # Build headers dict for gateways that need extra headers (e.g. Cashfree timestamp)
    webhook_headers = dict(request.headers)

    if not signature or not PaymentService.verify_webhook_signature(raw_body, signature, webhook_headers):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    data = await request.json()

    # Determine event name
    if gateway.name == "razorpay":
        event = data.get("event", "")
    else:
        event = data.get("type", "")

    try:
        PaymentService.process_webhook(event, data)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return {"status": "error"}


@router.get("/my-payments")
def get_my_payments(current_user: dict = Depends(get_current_user)):
    """Fetch authenticated user's payment history."""
    from core.database import get_supabase
    sb = get_supabase()
    if not sb:
        raise HTTPException(status_code=500, detail="Database unavailable")
    result = sb.table("payments").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return result.data if result.data else []


@router.get("/gateway-info")
def get_gateway_info():
    """Returns the active payment gateway name so the frontend knows which SDK to load."""
    gateway = get_payment_gateway()
    return {"gateway": gateway.name}
