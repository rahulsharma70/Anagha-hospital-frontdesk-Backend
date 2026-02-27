"""
Payment Service — gateway-agnostic payment operations.
Uses the gateway abstraction layer so all logic works with both Razorpay and Cashfree.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import HTTPException
from core.database import get_supabase
from core.config import settings
from services.gateways import get_payment_gateway

logger = logging.getLogger(__name__)

# Platform commission: hospital gets 90%, platform keeps 10%
PLATFORM_COMMISSION_RATE = 0.10


class PaymentService:
    """Gateway-agnostic payment service."""

    @staticmethod
    def _get_db():
        db = get_supabase()
        if not db:
            raise HTTPException(status_code=500, detail="Database unavailable")
        return db

    # ── Create Order (for appointments / operations) ────────
    @classmethod
    def create_order(
        cls,
        booking_id: int,
        booking_type: str,
        amount: float,
        user_id: Optional[int] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a payment order via the configured gateway."""
        supabase = cls._get_db()
        gateway = get_payment_gateway()

        receipt = f"{booking_type[:3].upper()}_{booking_id}"
        notes = {"booking_type": booking_type, "booking_id": str(booking_id)}
        if user_id:
            notes["user_id"] = str(user_id)

        # Call the gateway-agnostic create_order
        order = gateway.create_order(
            amount=amount,
            currency="INR",
            receipt=receipt,
            notes=notes,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
        )

        # Save payment record in DB
        payment_record: Dict[str, Any] = {
            "user_id": user_id,
            "amount": str(amount),
            "currency": "INR",
            "payment_method": gateway.name,
            "status": "PENDING",
            "razorpay_order_id": order["order_id"],
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
            "order_id": order["order_id"],
            "amount": float(amount),
            "gateway": gateway.name,
            "gateway_config": order.get("gateway_config", {}),
        }

    # ── Create Order for Hospital Registration ──────────────
    @classmethod
    def create_hospital_order(
        cls,
        plan_name: str,
        amount: float,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a payment order for hospital plan registration."""
        supabase = cls._get_db()
        gateway = get_payment_gateway()

        import re
        clean_plan = re.sub(r'[^A-Za-z0-9_-]', '', plan_name)
        receipt = f"HOSP_REG_{clean_plan}_{int(datetime.now().timestamp())}"
        notes = {"type": "hospital_registration", "plan": clean_plan}

        order = gateway.create_order(
            amount=amount,
            currency="INR",
            receipt=receipt,
            notes=notes,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
        )

        # Save payment record
        payment_record: Dict[str, Any] = {
            "amount": str(amount),
            "currency": "INR",
            "payment_method": gateway.name,
            "status": "PENDING",
            "razorpay_order_id": order["order_id"],
            "metadata": {"type": "hospital_registration", "plan": plan_name},
        }

        result = supabase.table("payments").insert(payment_record).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to save payment")

        return {
            "payment_id": result.data[0]["id"],
            "order_id": order["order_id"],
            "amount": float(amount),
            "gateway": gateway.name,
            "gateway_config": order.get("gateway_config", {}),
        }

    # ── Webhook Verification ────────────────────────────────
    @classmethod
    def verify_webhook_signature(
        cls, raw_body: bytes, signature: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Verify incoming webhook from the configured gateway."""
        gateway = get_payment_gateway()
        return gateway.verify_webhook_signature(raw_body, signature, headers)

    # ── Process Webhook Event ───────────────────────────────
    @classmethod
    def process_webhook(cls, event: str, payload_data: Dict[str, Any]):
        """
        Process a verified webhook event.
        Works for both Razorpay and Cashfree webhook shapes.
        """
        supabase = cls._get_db()
        gateway = get_payment_gateway()

        # ── Extract order/payment IDs based on gateway ──
        if gateway.name == "razorpay":
            payment_entity = (
                payload_data.get("payload", {}).get("payment", {}).get("entity", {})
            )
            gw_order_id = payment_entity.get("order_id")
            gw_payment_id = payment_entity.get("id")
            is_captured = event == "payment.captured"
        else:  # cashfree
            order_data = payload_data.get("data", {}).get("order", {})
            payment_data = payload_data.get("data", {}).get("payment", {})
            gw_order_id = order_data.get("order_id") or payload_data.get("data", {}).get("order_id")
            gw_payment_id = payment_data.get("cf_payment_id", "")
            is_captured = payload_data.get("type") == "PAYMENT_SUCCESS_WEBHOOK"

        if not gw_order_id:
            logger.warning("Webhook: no order ID found, skipping")
            return

        if not is_captured:
            logger.info(f"Webhook event '{event}' is not a capture event, skipping")
            return

        # ── Find payment in DB ──
        db_payment = (
            supabase.table("payments")
            .select("*")
            .eq("razorpay_order_id", gw_order_id)
            .execute()
        )
        if not db_payment.data:
            logger.warning(f"No payment found for gateway order {gw_order_id}")
            return

        p_data = db_payment.data[0]

        # ── Update payment status ──
        supabase.table("payments").update({
            "status": "COMPLETED",
            "razorpay_payment_id": str(gw_payment_id),
        }).eq("id", p_data["id"]).execute()

        # ── Confirm linked appointment ──
        if p_data.get("appointment_id"):
            supabase.table("appointments").update({"status": "confirmed"}).eq(
                "id", p_data["appointment_id"]
            ).execute()

        # ── Sub-merchant split (90/10 commission) ──
        cls._process_split(p_data, gw_payment_id)

    @classmethod
    def _process_split(cls, p_data: Dict[str, Any], gw_payment_id: str):
        """Execute the 90/10 sub-merchant split if hospital has a linked account."""
        supabase = cls._get_db()
        gateway = get_payment_gateway()

        hospital_id = None
        if p_data.get("appointment_id"):
            apt = (
                supabase.table("appointments")
                .select("hospital_id")
                .eq("id", p_data["appointment_id"])
                .execute()
            )
            if apt.data:
                hospital_id = apt.data[0]["hospital_id"]

        if not hospital_id:
            return

        hosp = (
            supabase.table("hospitals")
            .select("linked_account_id")
            .eq("id", hospital_id)
            .execute()
        )
        linked_id = hosp.data[0].get("linked_account_id") if hosp.data else None

        if not linked_id:
            return

        amount_paise = int(float(p_data["amount"]) * 100)
        transfer_amt = int(amount_paise * (1 - PLATFORM_COMMISSION_RATE))

        result = gateway.create_transfer(
            payment_id=str(gw_payment_id),
            linked_account_id=linked_id,
            amount_paise=transfer_amt,
            notes={"payment_id": str(p_data["id"])},
        )
        if result:
            logger.info(f"Split transfer completed: {transfer_amt/100:.2f} INR to {linked_id}")
