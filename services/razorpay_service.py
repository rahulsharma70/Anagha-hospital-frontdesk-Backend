"""
Razorpay Payment Service
Handles payment order creation, webhook processing, and verification
"""

import os
import json
import hashlib
import time
from typing import Optional, Dict, Any
from datetime import datetime
from database import get_supabase
from payment_gateway import PaymentGateway
import logging

logger = logging.getLogger(__name__)

class RazorpayService:
    """Service for Razorpay payment operations"""
    
    @staticmethod
    def generate_idempotency_key(user_id: int, appointment_id: Optional[int] = None, 
                                  operation_id: Optional[int] = None) -> str:
        """
        Generate idempotency key for payment order
        
        Args:
            user_id: User ID
            appointment_id: Optional appointment ID
            operation_id: Optional operation ID
        
        Returns:
            Unique idempotency key
        """
        timestamp = int(time.time())
        reference_id = appointment_id or operation_id or 0
        hash_input = f"{user_id}_{reference_id}_{timestamp}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{user_id}_{reference_id}_{timestamp}_{hash_value}"
    
    @staticmethod
    def create_razorpay_order(amount: float, currency: str, user_id: int,
                              appointment_id: Optional[int] = None,
                              operation_id: Optional[int] = None,
                              hospital_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Create Razorpay order with idempotency
        
        Args:
            amount: Amount in rupees
            currency: Currency code (default: INR)
            user_id: User ID
            appointment_id: Optional appointment ID
            operation_id: Optional operation ID
            hospital_id: Optional hospital ID
        
        Returns:
            Order details or None if failed
        """
        # Generate idempotency key
        internal_transaction_id = RazorpayService.generate_idempotency_key(
            user_id, appointment_id, operation_id
        )
        
        # Prepare notes for Razorpay
        notes = {
            "user_id": str(user_id),
            "internal_reference_id": internal_transaction_id
        }
        if appointment_id:
            notes["appointment_id"] = str(appointment_id)
        if operation_id:
            notes["operation_id"] = str(operation_id)
        if hospital_id:
            notes["hospital_id"] = str(hospital_id)
        
        # Create receipt ID
        receipt_id = f"receipt_{internal_transaction_id}"
        
        # Create order via PaymentGateway
        order_result = PaymentGateway.create_order(
            amount=amount,
            currency=currency,
            receipt=receipt_id,
            notes=notes
        )
        
        if not order_result:
            return None
        
        # Add internal transaction ID to result
        order_result["internal_transaction_id"] = internal_transaction_id
        return order_result
    
    @staticmethod
    def verify_payment_from_razorpay(razorpay_payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch and verify payment details from Razorpay API
        
        Args:
            razorpay_payment_id: Razorpay payment ID
        
        Returns:
            Payment details from Razorpay or None if failed
        """
        return PaymentGateway.get_payment_details(razorpay_payment_id)
    
    @staticmethod
    def process_webhook_event(webhook_payload: Dict[str, Any], 
                             signature: str) -> Dict[str, Any]:
        """
        Process Razorpay webhook event
        
        Args:
            webhook_payload: Webhook payload from Razorpay
            signature: Webhook signature
        
        Returns:
            Processing result
        """
        # Verify webhook signature
        payload_str = json.dumps(webhook_payload, separators=(',', ':'))
        if not PaymentGateway.verify_webhook_signature(payload_str, signature):
            logger.error("Webhook signature verification failed")
            return {
                "success": False,
                "error": "Invalid webhook signature"
            }
        
        # Extract event details
        event_type = webhook_payload.get("event")
        entity = webhook_payload.get("payload", {}).get("payment", {}).get("entity", {})
        
        if not entity:
            logger.error("No payment entity in webhook payload")
            return {
                "success": False,
                "error": "No payment entity in webhook"
            }
        
        razorpay_payment_id = entity.get("id")
        razorpay_order_id = entity.get("order_id")
        webhook_id = webhook_payload.get("id")
        
        if not webhook_id:
            logger.error("No webhook ID in payload")
            return {
                "success": False,
                "error": "No webhook ID"
            }
        
        return {
            "success": True,
            "webhook_id": webhook_id,
            "event_type": event_type,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_order_id": razorpay_order_id,
            "payment_entity": entity,
            "webhook_payload": webhook_payload
        }
    
    @staticmethod
    def check_webhook_idempotency(webhook_id: str) -> bool:
        """
        Check if webhook has already been processed (idempotency check)
        
        Args:
            webhook_id: Razorpay webhook event ID
        
        Returns:
            True if already processed, False otherwise
        """
        supabase = get_supabase()
        if not supabase:
            return False
        
        try:
            result = supabase.table("payment_webhooks").select("id, processed").eq(
                "webhook_id", webhook_id
            ).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("processed", False)
            return False
        except Exception as e:
            logger.error(f"Error checking webhook idempotency: {e}")
            return False
    
    @staticmethod
    def save_webhook_event(webhook_id: str, event_type: str, 
                          payment_id: Optional[int],
                          razorpay_payment_id: Optional[str],
                          razorpay_order_id: Optional[str],
                          webhook_payload: Dict[str, Any],
                          signature_verified: bool = True) -> Optional[int]:
        """
        Save webhook event to database
        
        Args:
            webhook_id: Razorpay webhook event ID
            event_type: Event type (e.g., 'payment.captured')
            payment_id: Internal payment ID
            razorpay_payment_id: Razorpay payment ID
            razorpay_order_id: Razorpay order ID
            webhook_payload: Full webhook payload
            signature_verified: Whether signature was verified
        
        Returns:
            Webhook record ID or None if failed
        """
        supabase = get_supabase()
        if not supabase:
            return None
        
        try:
            webhook_record = {
                "webhook_id": webhook_id,
                "event_type": event_type,
                "payment_id": payment_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_order_id": razorpay_order_id,
                "webhook_payload": webhook_payload,
                "signature_verified": signature_verified,
                "processed": False
            }
            
            result = supabase.table("payment_webhooks").insert(webhook_record).execute()
            if result.data:
                return result.data[0].get("id")
            return None
        except Exception as e:
            logger.error(f"Error saving webhook event: {e}")
            return None
    
    @staticmethod
    def mark_webhook_processed(webhook_id: str, payment_id: Optional[int] = None,
                               error: Optional[str] = None) -> bool:
        """
        Mark webhook as processed
        
        Args:
            webhook_id: Razorpay webhook event ID
            payment_id: Internal payment ID (if successfully processed)
            error: Error message (if processing failed)
        
        Returns:
            True if successful, False otherwise
        """
        supabase = get_supabase()
        if not supabase:
            return False
        
        try:
            update_data = {
                "processed": True,
                "processed_at": datetime.now().isoformat()
            }
            if payment_id:
                update_data["payment_id"] = payment_id
            if error:
                update_data["processing_error"] = error
            
            result = supabase.table("payment_webhooks").update(update_data).eq(
                "webhook_id", webhook_id
            ).execute()
            
            return result.data is not None and len(result.data) > 0
        except Exception as e:
            logger.error(f"Error marking webhook as processed: {e}")
            return False

