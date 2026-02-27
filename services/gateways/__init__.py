"""
Payment Gateway Factory
Reads PAYMENT_GATEWAY from settings and returns the appropriate implementation.
"""

import logging
from core.config import settings
from .base import PaymentGatewayBase

logger = logging.getLogger(__name__)


def get_payment_gateway() -> PaymentGatewayBase:
    """
    Returns the configured payment gateway.

    Controlled by PAYMENT_GATEWAY env var:
      - "razorpay" (default)
      - "cashfree"
    """
    gw_name = settings.PAYMENT_GATEWAY.lower().strip()

    if gw_name == "cashfree":
        from .cashfree import CashfreeGateway
        gw = CashfreeGateway()
    else:
        from .razorpay import RazorpayGateway
        gw = RazorpayGateway()

    logger.info(f"🔌 Payment gateway initialized: {gw.name}")
    return gw
