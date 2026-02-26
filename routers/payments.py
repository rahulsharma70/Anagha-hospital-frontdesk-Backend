from fastapi import APIRouter, Depends, HTTPException, status, Request
from dependencies.auth import get_current_user, get_current_doctor
from services.payment_service import PaymentService
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/payments", tags=["payments"])

class OrderCreate(BaseModel):
    appointment_id: Optional[int] = None
    operation_id: Optional[int] = None
    amount: float
    currency: str = "INR"

@router.post("/create-order")
def create_payment_order(order_data: OrderCreate, current_user: Optional[dict] = Depends(lambda: None)):
    """Initialize a Razorpay split-payment order"""
    if not order_data.appointment_id and not order_data.operation_id:
        raise HTTPException(status_code=400, detail="Booking ID required")
        
    booking_id = order_data.appointment_id or order_data.operation_id
    b_type = "appointment" if order_data.appointment_id else "operation"
    
    return PaymentService.create_razorpay_order(
        booking_id=booking_id,
        booking_type=b_type,
        amount=order_data.amount,
        user_id=current_user["id"] if current_user else None
    )

@router.post("/webhook")
async def razorpay_webhook_receiver(request: Request):
    """Secure Webhook handler for Razorpay Payment events"""
    payload_body = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    
    if not signature or not PaymentService.verify_webhook_signature(payload_body, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    data = await request.json()
    event = data.get("event")
    
    try:
        PaymentService.process_webhook(event, data)
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error"}

@router.get("/my-payments")
def get_my_payments(current_user: dict = Depends(get_current_user)):
    """Fetch user payments"""
    from core.database import get_supabase
    sb = get_supabase()
    result = sb.table("payments").select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return result.data if result.data else []
