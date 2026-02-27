"""
Razorpay Payment Gateway Implementation
"""

import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import requests
from core.config import settings
from .base import PaymentGatewayBase

logger = logging.getLogger(__name__)

RAZORPAY_BASE_URL = "https://api.razorpay.com/v1"


class RazorpayGateway(PaymentGatewayBase):
    """Razorpay implementation of the payment gateway."""

    def __init__(self):
        self._key_id = settings.RAZORPAY_KEY_ID
        self._key_secret = settings.RAZORPAY_KEY_SECRET
        self._webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
        if self._key_id and self._key_secret:
            logger.info("✅ Razorpay gateway credentials loaded")
        else:
            logger.warning("⚠️ Razorpay credentials missing")

    @property
    def name(self) -> str:
        return "razorpay"

    # ── helpers ──────────────────────────────────────────────
    @property
    def _auth(self):
        return (self._key_id, self._key_secret)

    # ── create_order ────────────────────────────────────────
    def create_order(
        self,
        amount: float,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._key_id or not self._key_secret:
            raise RuntimeError("Razorpay credentials not configured")

        payload = {
            "amount": int(amount * 100),  # paise
            "currency": currency,
            "receipt": receipt or f"rcpt_{int(datetime.now().timestamp())}",
            "payment_capture": 1,
            "notes": notes or {},
        }

        resp = requests.post(
            f"{RAZORPAY_BASE_URL}/orders",
            auth=self._auth,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            logger.error(f"Razorpay create_order failed: {resp.text}")
            raise RuntimeError(f"Razorpay error: {resp.text}")

        order = resp.json()
        return {
            "order_id": order["id"],
            "amount": amount,
            "currency": currency,
            "gateway": self.name,
            "gateway_config": {
                "key_id": self._key_id,
                "razorpay_order_id": order["id"],
            },
        }

    # ── verify_webhook_signature ────────────────────────────
    def verify_webhook_signature(
        self, raw_body: bytes, signature: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        if not self._webhook_secret:
            logger.warning("Razorpay webhook secret not configured")
            return False
        expected = hmac.new(
            self._webhook_secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── get_payment_details ─────────────────────────────────
    def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        if not self._key_id or not self._key_secret:
            return None
        try:
            resp = requests.get(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}",
                auth=self._auth,
                timeout=15,
            )
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.error(f"Razorpay get_payment_details error: {e}")
            return None

    # ── create_refund ───────────────────────────────────────
    def create_refund(
        self, payment_id: str, amount: Optional[float] = None, notes: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        if not self._key_id or not self._key_secret:
            return None
        payload: Dict[str, Any] = {"notes": notes or {}}
        if amount:
            payload["amount"] = int(amount * 100)
        try:
            resp = requests.post(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}/refund",
                auth=self._auth,
                json=payload,
                timeout=15,
            )
            return resp.json() if resp.status_code in (200, 201) else None
        except Exception as e:
            logger.error(f"Razorpay refund error: {e}")
            return None

    # ── create_transfer (Route / split) ─────────────────────
    def create_transfer(
        self,
        payment_id: str,
        linked_account_id: str,
        amount_paise: int,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "transfers": [
                {
                    "account": linked_account_id,
                    "amount": amount_paise,
                    "currency": "INR",
                    "notes": notes or {},
                }
            ]
        }
        try:
            resp = requests.post(
                f"{RAZORPAY_BASE_URL}/payments/{payment_id}/transfers",
                auth=self._auth,
                json=payload,
                timeout=15,
            )
            return resp.json() if resp.status_code in (200, 201) else None
        except Exception as e:
            logger.error(f"Razorpay transfer error: {e}")
            return None
