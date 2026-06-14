"""Payments router — checkout & verify.

``POST /api/payments/verify`` performs **real** on-chain USDC verification on
Base (see :mod:`app.services.payment`) and persists a ``payments`` row.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter

from ..models.schemas import CheckoutRequest, CheckoutResponse, VerifyRequest, VerifyResponse
from ..services import payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse,
             summary="Create a payment checkout session")
async def checkout(body: CheckoutRequest):
    """Create a checkout session.

    Returns the configured USDC receive address on Base + an expiry. Persisting
    a ``payments`` row happens at verification time (once the tx hash is known).
    """
    session = payment.create_checkout(
        report_id=body.report_id,
        coingecko_id=body.coingecko_id,
        wallet_address=body.wallet_address,
        amount=body.amount,
        token=body.token,
        chain=body.chain,
    )
    return CheckoutResponse(
        checkout_id=session["checkout_id"],
        wallet_address=session["payment_address"],
        amount=session["amount"],
        token=session["token"],
        chain=session["chain"],
        expires_at=datetime.fromisoformat(session["expires_at"]),
        status=session["status"],
    )


@router.post("/verify", response_model=VerifyResponse,
             summary="Verify an on-chain USDC payment on Base")
async def verify(body: VerifyRequest):
    """Verify a payment by tx hash against the Base blockchain.

    Looks up ``eth_getTransactionReceipt`` on Base, checks for a USDC
    ``Transfer`` event from ``wallet_address`` of the expected ``amount``, and
    records a verified ``payments`` row on success.
    """
    result = await payment.verify_payment(
        tx_hash=body.tx_hash,
        wallet_address=body.wallet_address,
        amount=body.amount,
        token=body.token,
        chain=body.chain,
        report_id=None,
    )
    return VerifyResponse(
        verified=result["verified"],
        tx_hash=result["tx_hash"],
        message=result["message"],
    )
