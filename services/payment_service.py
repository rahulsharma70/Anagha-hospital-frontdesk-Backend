import os
import hmac
import hashlib
from typing import Dict, Any, Optional, Tuple
from fastapi import HTTPException
from core.database import get_supabase
from core.config import settings
import requests

class PaymentService:
    @staticmethod
    def _get_db():
        return get_supabase()

    @classmethod
    def create_razorpay_order(cls, booking_id: int, booking_type: str, amount: float, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Creates Razorpay Order and Payment Record"""
        supabase = cls._get_db()
        key_id = os.getenv("RAZORPAY_KEY_ID")
        key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        
        if not key_id or not key_secret:
            raise HTTPException(status_code=500, detail="Razorpay credentials not configured")

        # Create Order via Razorpay API
        auth = (key_id, key_secret)
        order_payload = {
            "amount": int(amount * 100), # in paise
            "currency": "INR",
            "receipt": f"{booking_type[:3].upper()}_{booking_id}",
            "payment_capture": 1
        }
        
        resp = requests.post("https://api.razorpay.com/v1/orders", json=order_payload, auth=auth)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Razorpay Error: {resp.text}")
            
        data = resp.json()
        
        rp_order_id = data["id"]
        
        payment_record = {
            "user_id": user_id,
            "amount": str(amount),
            "currency": "INR",
            "payment_method": "razorpay",
            "status": "PENDING",
            "razorpay_order_id": rp_order_id,
        }
        
        if booking_type == "appointment":
            payment_record["appointment_id"] = booking_id
        else:
            payment_record["operation_id"] = booking_id
            
        result = supabase.table("payments").insert(payment_record).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save payment")

        return {
            "payment_id": result.data[0]["id"],
            "order_id": rp_order_id,
            "amount": float(amount),
            "key_id": key_id
        }

    @classmethod
    def verify_webhook_signature(cls, payload_body: bytes, signature: str) -> bool:
        secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
        if not secret:
            return False
            
        expected_sig = hmac.new(
            secret.encode(),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_sig, signature)

    @classmethod
    def process_webhook(cls, event: str, payload_data: Dict[str, Any]):
        """Complete the payment verify workflow based on Webhooks securely"""
        supabase = cls._get_db()
        
        if event == "payment.captured":
            payment_entity = payload_data.get("payload", {}).get("payment", {}).get("entity", {})
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            
            if not order_id: return
            
            # Find payment in DB
            db_payment = supabase.table("payments").select("*").eq("razorpay_order_id", order_id).execute()
            if not db_payment.data:
                return
            
            p_data = db_payment.data[0]
            
            # Update Payment
            supabase.table("payments").update({
                "status": "COMPLETED",
                "razorpay_payment_id": payment_id
            }).eq("id", p_data["id"]).execute()
            
            # Update Appointment Status
            if p_data.get("appointment_id"):
                supabase.table("appointments").update({"status": "confirmed"}).eq("id", p_data["appointment_id"]).execute()
                
            # Perform Razorpay Route Transfer for Sub-merchant division
            hospital_id = None
            if p_data.get("appointment_id"):
                apt = supabase.table("appointments").select("hospital_id").eq("id", p_data["appointment_id"]).execute()
                if apt.data: hospital_id = apt.data[0]["hospital_id"]
                
            if hospital_id:
                hosp = supabase.table("hospitals").select("linked_account_id").eq("id", hospital_id).execute()
                linked_id = hosp.data[0].get("linked_account_id") if hosp.data else None
                
                if linked_id:
                    # Platform commission = 10%
                    amount_paise = int(float(p_data["amount"]) * 100)
                    transfer_amt = int(amount_paise * 0.90) 
                    
                    auth = (os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
                    transfer_payload = {
                        "transfers": [
                            {
                                "account": linked_id,
                                "amount": transfer_amt,
                                "currency": "INR",
                                "notes": {"payment_id": p_data["id"]}
                            }
                        ]
                    }
                    requests.post(f"https://api.razorpay.com/v1/payments/{payment_id}/transfers", json=transfer_payload, auth=auth)
