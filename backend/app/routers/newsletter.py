"""Newsletter router — email subscriptions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from .. import db
from ..models.schemas import NewsletterResponse, NewsletterSubscribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


@router.post("/subscribe", response_model=NewsletterResponse,
             summary="Subscribe an email to the newsletter")
async def subscribe(body: NewsletterSubscribe):
    """Store an email subscription in `newsletter_subscriptions`.

    - Idempotent: re-subscribing an existing email returns success rather than
      an error (status reset to `active`, tier preserved unless changed).
    - Email uniqueness is enforced at the DB level.
    """
    email = body.email.lower().strip()

    # Upsert: if the email exists, bump it back to active (and update tier/wallet).
    existing = await db.fetchrow(
        "SELECT id, tier FROM newsletter_subscriptions WHERE email = $1", email
    )
    if existing is not None:
        await db.execute(
            """
            UPDATE newsletter_subscriptions
               SET status = 'active',
                   tier = $2,
                   wallet_address = COALESCE($3, wallet_address)
             WHERE email = $1
            """,
            email, body.tier, body.wallet_address,
        )
        return NewsletterResponse(
            subscribed=True,
            email=email,
            tier=existing["tier"],
            message="You're already subscribed — we've re-activated your account.",
        )

    try:
        await db.execute(
            """
            INSERT INTO newsletter_subscriptions (email, tier, wallet_address, status)
            VALUES ($1, $2, $3, 'active')
            """,
            email, body.tier, body.wallet_address,
        )
    except Exception as exc:
        logger.error("Newsletter insert failed for %s: %s", email, exc)
        raise HTTPException(status_code=409, detail="Email already subscribed")

    return NewsletterResponse(
        subscribed=True,
        email=email,
        tier=body.tier,
        message="Subscribed! Welcome to Lisa's Assets. 🎉",
    )
