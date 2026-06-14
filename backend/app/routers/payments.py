"""Payments router — checkout & verify (stubs for issue #6).

The real on-chain verification lands later; these endpoints provide a stable,
documented contract for the frontend.
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
             summary="Create a payment checkout session (stub)")
async def checkout(body: CheckoutRequest):
    """Create a stub checkout session.

    Returns a deterministic placeholder payment address + expiry. A real
    implementation will generate a unique receive address per checkout and
    persist a `payments` row with status=`awaiting_payment`.
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
             summary="Verify an on-chain payment (stub)")
async def verify(body: VerifyRequest):
    """Verify a payment by tx hash.

    **Stub** — always returns ``verified=False`` for now. The verifier service
    will look up the transaction on-chain and flip the associated report to
    `public` once confirmed.
    """
    result = await payment.verify_payment(
        tx_hash=body.tx_hash,
        wallet_address=body.wallet_address,
        amount=body.amount,
        token=body.token,
        chain=body.chain,
    )
    return VerifyResponse(
        verified=result["verified"],
        tx_hash=result["tx_hash"],
        message=result["message"],
    )
