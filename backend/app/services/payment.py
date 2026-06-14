"""Payment service — STUB.

Issue #6 payments. Real on-chain verification (Base/ETH tx lookup, token-balance
discounts) will be wired in later. For now these helpers return deterministic
placeholder data so the API surface is complete and documented.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


# Price table (USD) — stub values, to be replaced by a real pricing module.
REPORT_PRICE_USD: float = 25.0
DISCOUNT_TOKEN_THRESHOLD: float = 10_000.0  # $LISA tokens for discount
DISCOUNT_RATE: float = 0.5  # 50% off


def compute_price(wallet_address: str | None, token_balance: float = 0.0) -> dict[str, Any]:
    """Compute the price for a single report, applying any token discount."""
    discount_applied = token_balance >= DISCOUNT_TOKEN_THRESHOLD
    amount = REPORT_PRICE_USD
    if discount_applied:
        amount *= DISCOUNT_RATE
    return {
        "amount": round(amount, 2),
        "currency": "USDC",
        "chain": "base",
        "discount_applied": discount_applied,
        "discount_rate": DISCOUNT_RATE if discount_applied else 0.0,
    }


def create_checkout(*, report_id: str | None, coingecko_id: str | None,
                    wallet_address: str, amount: float, token: str,
                    chain: str) -> dict[str, Any]:
    """Build a stub checkout payload."""
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    return {
        "checkout_id": str(uuid.uuid4()),
        "report_id": report_id,
        "coingecko_id": coingecko_id,
        "wallet_address": wallet_address,
        "amount": amount,
        "token": token,
        "chain": chain,
        "expires_at": expires.isoformat(),
        "status": "awaiting_payment",
        "payment_address": "0xLISA_RECEIVE_ADDRESS_TBD",
    }


async def verify_payment(*, tx_hash: str, wallet_address: str, amount: float,
                         token: str, chain: str) -> dict[str, Any]:
    """STUB verification.

    A real implementation will:
      * look up `tx_hash` on the relevant chain,
      * confirm the recipient address, amount and token,
      * mark the payment row verified + unlock the report.

    For now we always return ``verified=False`` with an explanatory message.
    """
    return {
        "verified": False,
        "tx_hash": tx_hash,
        "message": (
            "On-chain verification not yet implemented. "
            "Payment recorded and will be verified once the verifier service "
            "is deployed."
        ),
    }
