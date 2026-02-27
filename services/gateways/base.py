"""
Payment Gateway Abstraction Layer
Defines the contract that all payment gateways must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PaymentGatewayBase(ABC):
    """Abstract base class for payment gateways (Razorpay, Cashfree, etc.)"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the gateway name, e.g. 'razorpay' or 'cashfree'"""
        ...

    @abstractmethod
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
        """
        Create a payment order.

        Must return a dict with AT LEAST:
          - order_id: str          (gateway order id)
          - amount: float          (in rupees)
          - currency: str
          - gateway: str           (gateway name)
          - gateway_config: dict   (keys / session ids needed by frontend)
        """
        ...

    @abstractmethod
    def verify_webhook_signature(
        self, raw_body: bytes, signature: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        """Verify an incoming webhook signature. Return True if valid."""
        ...

    @abstractmethod
    def get_payment_details(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch payment details from the gateway by its gateway-specific payment ID."""
        ...

    @abstractmethod
    def create_refund(
        self, payment_id: str, amount: Optional[float] = None, notes: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Issue a refund (full or partial)."""
        ...

    def create_transfer(
        self,
        payment_id: str,
        linked_account_id: str,
        amount_paise: int,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Transfer funds to a sub-merchant / vendor (for commission splits).
        Override in gateways that support Route / Split Payments.
        """
        logger.warning(f"{self.name} does not implement create_transfer")
        return None
