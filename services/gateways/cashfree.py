"""
Cashfree Payment Gateway Implementation
Uses Cashfree PG API v2023-08-01 (REST, no SDK dependency).
"""

import hmac
import hashlib
import base64
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import requests
from core.config import settings
from .base import PaymentGatewayBase

logger = logging.getLogger(__name__)


class CashfreeGateway(PaymentGatewayBase):
    """Cashfree implementation of the payment gateway."""

    API_VERSION = "2023-08-01"

    def __init__(self):
        self._client_id = settings.CASHFREE_CLIENT_ID
        self._client_secret = settings.CASHFREE_CLIENT_SECRET
        env = settings.CASHFREE_ENVIRONMENT.lower().strip()
        if env.startswith("prod"):
            self._base_url = "https://api.cashfree.com/pg"
        else:
            self._base_url = "https://sandbox.cashfree.com/pg"
        if self._client_id and self._client_secret:
            logger.info(f"✅ Cashfree gateway loaded (env={env})")
        else:
            logger.warning("⚠️ Cashfree credentials missing")

    @property
    def name(self) -> str:
        return "cashfree"

    # ── common headers ──────────────────────────────────────
    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-client-id": self._client_id,
            "x-client-secret": self._client_secret,
            "x-api-version": self.API_VERSION,
        }

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
        if not self._client_id or not self._client_secret:
            raise RuntimeError("Cashfree credentials not configured")

        order_id = receipt or f"order_{int(datetime.now().timestamp())}"

        payload: Dict[str, Any] = {
            "order_id": order_id,
            "order_amount": float(f"{amount:.2f}"),
            "order_currency": currency,
            "customer_details": {
                "customer_id": f"cust_{int(datetime.now().timestamp())}",
                "customer_phone": customer_phone or "9999999999",
            },
        }

        # Cashfree production requires https return_url; skip for local dev
        frontend_url = settings.FRONTEND_URL
        if frontend_url.startswith("https"):
            payload["order_meta"] = {
                "return_url": f"{frontend_url}/payment-status?order_id={order_id}",
            }

        if customer_name:
            payload["customer_details"]["customer_name"] = customer_name
        if customer_email:
            payload["customer_details"]["customer_email"] = customer_email
        if notes:
            payload["order_tags"] = {k: str(v) for k, v in notes.items()}

        resp = requests.post(
            f"{self._base_url}/orders",
            headers=self._headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            logger.error(f"Cashfree create_order failed: {resp.text}")
            raise RuntimeError(f"Cashfree error: {resp.text}")

        data = resp.json()
        return {
            "order_id": data.get("order_id", order_id),
            "amount": amount,
            "currency": currency,
            "gateway": self.name,
            "gateway_config": {
                "payment_session_id": data.get("payment_session_id"),
                "cf_order_id": data.get("cf_order_id"),
                "order_id": data.get("order_id", order_id),
                "environment": settings.CASHFREE_ENVIRONMENT,
            },
        }

    # ── verify_webhook_signature ────────────────────────────
    def verify_webhook_signature(
        self, raw_body: bytes, signature: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """
        Cashfree webhook verification:
          signature = base64( HMAC-SHA256( timestamp + rawBody, secret ) )
        """
        if not self._client_secret:
            logger.warning("Cashfree client secret not configured for webhook verification")
            return False

        timestamp = ""
        if headers:
            timestamp = headers.get("x-webhook-timestamp", "")

        message = timestamp.encode() + raw_body
        computed = hmac.new(
            self._client_secret.encode(), message, hashlib.sha256
        ).digest()
        computed_b64 = base64.b64encode(computed).decode()

        return hmac.compare_digest(computed_b64, signature)

    # ── get_payment_details ─────────────────────────────────
    def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch order/payment details by order_id from Cashfree."""
        try:
            resp = requests.get(
                f"{self._base_url}/orders/{payment_id}",
                headers=self._headers,
                timeout=15,
            )
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            logger.error(f"Cashfree get_payment_details error: {e}")
            return None

    # ── create_refund ───────────────────────────────────────
    def create_refund(
        self, payment_id: str, amount: Optional[float] = None, notes: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "refund_id": f"refund_{int(datetime.now().timestamp())}",
            "refund_amount": amount if amount else 0,
            "refund_note": (notes or {}).get("reason", "Refund"),
        }
        try:
            resp = requests.post(
                f"{self._base_url}/orders/{payment_id}/refunds",
                headers=self._headers,
                json=payload,
                timeout=15,
            )
            return resp.json() if resp.status_code in (200, 201) else None
        except Exception as e:
            logger.error(f"Cashfree refund error: {e}")
            return None

    # ── create_transfer (Cashfree Split / Easy Split) ───────
    def create_transfer(
        self,
        payment_id: str,
        linked_account_id: str,
        amount_paise: int,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Cashfree uses vendor splits at order creation time, not post-payment.
        For post-payment settlements, use the Cashfree settlements API.
        This is a placeholder that logs a warning.
        """
        logger.info(
            f"Cashfree split: vendor={linked_account_id}, "
            f"amount={amount_paise/100:.2f} INR for order {payment_id}"
        )
        # In production you'd configure vendors via Cashfree dashboard
        # and pass split details during order creation.
        return {"status": "logged", "vendor": linked_account_id, "amount": amount_paise}
