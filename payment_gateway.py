"""
Payment Gateway Integration Module
Supports Razorpay (primary) and UPI fallback
"""

import os
import hmac
import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import requests
import logging

# Load environment variables
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
parent_env_path = Path(__file__).parent.parent.parent / ".env"
if parent_env_path.exists():
    load_dotenv(parent_env_path, override=True)
if env_path.exists():
    load_dotenv(env_path, override=True)
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Razorpay Configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"

# Log Razorpay config status
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    logger.info("✅ Razorpay credentials loaded successfully")
else:
    logger.warning("⚠️ Razorpay credentials not configured, using UPI fallback")

class PaymentGateway:
    """Payment Gateway handler for Razorpay and UPI"""
    
    @staticmethod
    def create_order(amount: float, currency: str = "INR", receipt: Optional[str] = None, 
                     notes: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Create a payment order using Razorpay
        
        Args:
            amount: Amount in rupees (will be converted to paise)
            currency: Currency code (default: INR)
            receipt: Receipt ID (optional)
            notes: Additional notes (optional)
        
        Returns:
            Order details or None if failed
        """
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            print("⚠️ Razorpay credentials not configured, using UPI fallback")
            return PaymentGateway._create_upi_order(amount, receipt, notes)
        
        try:
            amount_in_paise = int(amount * 100)  # Convert to paise
            
            payload = {
                "amount": amount_in_paise,
                "currency": currency,
                "receipt": receipt or f"receipt_{int(datetime.now().timestamp())}",
                "notes": notes or {}
            }
            
            response = requests.post(
                f"{RAZORPAY_BASE_URL}/orders",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200 or response.status_code == 201:
                order_data = response.json()
                return {
                    "order_id": order_data.get("id"),
                    "amount": amount,
                    "currency": currency,
                    "status": "created",
                    "razorpay_order_id": order_data.get("id"),
                    "key_id": RAZORPAY_KEY_ID,
                }
            else:
                print(f"Razorpay order creation failed: {response.text}")
                return PaymentGateway._create_upi_order(amount, receipt, notes)
                
        except Exception as e:
            print(f"Error creating Razorpay order: {e}")
            return PaymentGateway._create_upi_order(amount, receipt, notes)
    
    @staticmethod
    def _create_upi_order(amount: float, receipt: Optional[str], notes: Optional[Dict]) -> Dict[str, Any]:
        """Create a UPI-based order (fallback when Razorpay not configured)"""
        order_id = f"UPI_{int(datetime.now().timestamp())}"
        return {
            "order_id": order_id,
            "amount": amount,
            "currency": "INR",
            "status": "created",
            "payment_method": "upi",
            "upi_order": True,
        }
    
    @staticmethod
    def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
        """
        Verify Razorpay payment signature (for frontend payment verification)
        
        Args:
            razorpay_order_id: Razorpay order ID
            razorpay_payment_id: Razorpay payment ID
            razorpay_signature: Payment signature from Razorpay
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not RAZORPAY_KEY_SECRET:
            # For UPI orders, accept if order_id starts with UPI_
            if razorpay_order_id.startswith("UPI_"):
                return True
            return False
        
        try:
            message = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                RAZORPAY_KEY_SECRET.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(generated_signature, razorpay_signature)
        except Exception as e:
            logger.error(f"Error verifying payment signature: {e}")
            return False
    
    @staticmethod
    def verify_webhook_signature(payload: str, signature: str) -> bool:
        """
        Verify Razorpay webhook signature
        
        Args:
            payload: Raw webhook payload (string)
            signature: Webhook signature from X-Razorpay-Signature header
        
        Returns:
            True if signature is valid, False otherwise
        """
        if not RAZORPAY_WEBHOOK_SECRET:
            logger.warning("Razorpay webhook secret not configured")
            return False
        
        try:
            generated_signature = hmac.new(
                RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(generated_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    @staticmethod
    def get_payment_details(payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment details from Razorpay"""
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            return None
        
        try:
            response = requests.get(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error getting payment details: {e}")
            return None
    
    @staticmethod
    def create_refund(payment_id: str, amount: Optional[float] = None, 
                      notes: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Create a refund for a payment
        
        Args:
            payment_id: Razorpay payment ID
            amount: Refund amount (None for full refund)
            notes: Refund notes
        
        Returns:
            Refund details or None if failed
        """
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            print("⚠️ Razorpay not configured, cannot process refund")
            return None
        
        try:
            payload = {
                "notes": notes or {}
            }
            
            if amount:
                payload["amount"] = int(amount * 100)  # Convert to paise
            
            response = requests.post(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}/refund",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            return None
        except Exception as e:
            print(f"Error creating refund: {e}")
            return None
    
    @staticmethod
    def calculate_fee(service_type: str, hospital_id: int, 
                      specialty: Optional[str] = None) -> float:
        """
        Calculate fee for appointment or operation
        
        Args:
            service_type: 'appointment' or 'operation'
            hospital_id: Hospital ID
            specialty: Operation specialty (optional)
        
        Returns:
            Fee amount in rupees
        """
        # Default fees
        if service_type == "appointment":
            return 500.0  # ₹500 for appointment
        elif service_type == "operation":
            base_fee = 5000.0  # ₹5000 base for operation
            
            # Specialty-based pricing
            specialty_multipliers = {
                "surgery": 1.5,
                "ortho": 1.3,
                "gyn": 1.2,
                "cardio": 2.0,
            }
            
            if specialty and specialty.lower() in specialty_multipliers:
                return base_fee * specialty_multipliers[specialty.lower()]
            
            return base_fee
        
        return 0.0
