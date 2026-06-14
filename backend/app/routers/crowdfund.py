"""Crowdfunding pools router.

Lets a community pool USDC contributions toward the ``target_amount`` for a
project's Lisa Coefficient report. Once funded, the report becomes public for
everyone.

Endpoints
---------
* ``POST   /api/crowdfund/create``                  — open a pool for a project
* ``GET    /api/crowdfund/{pool_id}``               — pool details + progress
* ``POST   /api/crowdfund/{pool_id}/contribute``    — add a contribution
* ``GET    /api/crowdfund/project/{coingecko_id}``  — pool for a project
* ``GET    /api/crowdfund/discount/{wallet_address}`` — token discount check
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from .. import db
from ..models.schemas import (
    CrowdfundContribute,
    CrowdfundContributeResponse,
    CrowdfundCreate,
    CrowdfundPool,
    TokenDiscountResponse,
)
from ..services.token_balances import check_token_discount

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crowdfund", tags=["crowdfund"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _row_to_pool(row: Any) -> CrowdfundPool:
    """Map a crowdfund_pools row (with project join) to a response model."""
    target = float(row["target_amount"])
    current = float(row["current_amount"])
    progress = (current / target * 100.0) if target > 0 else 0.0
    return CrowdfundPool(
        id=str(row["id"]),
        project_id=str(row["project_id"]),
        coingecko_id=row.get("coingecko_id"),
        target_amount=target,
        current_amount=current,
        contributors_count=int(row["contributors_count"]),
        status=row["status"],
        report_id=str(row["report_id"]) if row.get("report_id") else None,
        created_at=row["created_at"],
        funded_at=row.get("funded_at"),
        progress_pct=round(progress, 2),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/create", response_model=CrowdfundPool,
             summary="Create a crowdfunding pool for a project")
async def create_pool(body: CrowdfundCreate):
    """Open a new crowdfunding pool.

    The project must already exist. A duplicate open pool for the same project
    is rejected so that funds are not split across competing pools.
    """
    project = await db.fetchrow(
        "SELECT id, coingecko_id FROM projects WHERE id::text = $1",
        body.project_id,
    )
    if project is None:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{body.project_id}' not found",
        )

    existing = await db.fetchrow(
        "SELECT id FROM crowdfund_pools "
        "WHERE project_id = $1 AND status = 'open'",
        project["id"],
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "An open crowdfunding pool already exists for this project: "
                f"{existing['id']}"
            ),
        )

    coingecko_id = body.coingecko_id or project.get("coingecko_id")
    row = await db.fetchrow(
        """
        INSERT INTO crowdfund_pools
            (project_id, coingecko_id, target_amount)
        VALUES ($1, $2, $3)
        RETURNING id, project_id, coingecko_id, target_amount,
                  current_amount, contributors_count, status, report_id,
                  created_at, funded_at
        """,
        project["id"], coingecko_id, float(body.target_amount),
    )
    return _row_to_pool(row)


@router.get("/{pool_id}", response_model=CrowdfundPool,
            summary="Get crowdfunding pool details with progress")
async def get_pool(pool_id: str):
    """Return a single crowdfunding pool, including funding progress."""
    row = await db.fetchrow(
        """
        SELECT id, project_id, coingecko_id, target_amount, current_amount,
               contributors_count, status, report_id, created_at, funded_at
        FROM crowdfund_pools
        WHERE id::text = $1
        """,
        pool_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Pool '{pool_id}' not found"
        )
    return _row_to_pool(row)


@router.post("/{pool_id}/contribute",
             response_model=CrowdfundContributeResponse,
             summary="Add a contribution to a pool")
async def contribute(pool_id: str, body: CrowdfundContribute):
    """Record a contribution to a pool.

    Adds the contribution row, bumps ``current_amount`` and the distinct
    contributor count, and flips the pool to ``funded`` (with ``funded_at``)
    once ``current_amount`` reaches ``target_amount``.
    """
    pool = await db.fetchrow(
        """
        SELECT id, project_id, target_amount, current_amount,
               contributors_count, status
        FROM crowdfund_pools
        WHERE id::text = $1
        """,
        pool_id,
    )
    if pool is None:
        raise HTTPException(
            status_code=404, detail=f"Pool '{pool_id}' not found"
        )
    if pool["status"] != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Pool is not open for contributions (status='{pool['status']}')",
        )

    amount = float(body.amount)
    if amount <= 0:
        raise HTTPException(
            status_code=400, detail="Contribution amount must be positive"
        )

    # Is this wallet already a contributor?
    already = await db.fetchval(
        "SELECT 1 FROM crowdfund_contributions "
        "WHERE pool_id = $1 AND wallet_address = $2 LIMIT 1",
        pool["id"], body.wallet_address,
    )

    # Insert the contribution.
    await db.execute(
        """
        INSERT INTO crowdfund_contributions (pool_id, wallet_address, amount, tx_hash)
        VALUES ($1, $2, $3, $4)
        """,
        pool["id"], body.wallet_address, amount, body.tx_hash,
    )

    # Update the running totals + status in one go.
    new_amount = float(pool["current_amount"]) + amount
    new_contrib_count = int(pool["contributors_count"]) + (0 if already else 1)
    new_status = "funded" if new_amount >= float(pool["target_amount"]) else "open"
    funded_clause = "funded_at = now()" if new_status == "funded" else "funded_at = NULL"
    await db.execute(
        f"""
        UPDATE crowdfund_pools
        SET current_amount = $1,
            contributors_count = $2,
            status = $3,
            {funded_clause}
        WHERE id = $4
        """,
        new_amount, new_contrib_count, new_status, pool["id"],
    )

    message = "Contribution recorded."
    if new_status == "funded":
        message = "Funding target reached — report will be unlocked."

    return CrowdfundContributeResponse(
        contributed=True,
        pool_id=str(pool["id"]),
        current_amount=round(new_amount, 2),
        contributors_count=new_contrib_count,
        status=new_status,
        message=message,
    )


@router.get("/project/{coingecko_id}", response_model=CrowdfundPool,
            summary="Get the crowdfunding pool for a project")
async def get_pool_by_project(coingecko_id: str):
    """Return the most recent pool for a project (by coingecko_id).

    Prefers an open pool; falls back to the latest pool of any status.
    """
    row = await db.fetchrow(
        """
        SELECT cp.id, cp.project_id, cp.coingecko_id, cp.target_amount,
               cp.current_amount, cp.contributors_count, cp.status,
               cp.report_id, cp.created_at, cp.funded_at
        FROM crowdfund_pools cp
        JOIN projects p ON p.id = cp.project_id
        WHERE p.coingecko_id = $1
        ORDER BY (cp.status = 'open') DESC, cp.created_at DESC
        LIMIT 1
        """,
        coingecko_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No crowdfunding pool found for project '{coingecko_id}'",
        )
    return _row_to_pool(row)


@router.get("/discount/{wallet_address}",
            response_model=TokenDiscountResponse,
            summary="Check token-based discount eligibility")
async def token_discount(wallet_address: str):
    """Check whether ``wallet_address`` qualifies for the token-holder discount.

    Looks up LISA (Base), SOONAK (Solana), and CRDD (Arbitrum) balances and
    returns the discount info. Requires the token contract/mint addresses to
    be configured via env vars.
    """
    info = await check_token_discount(wallet_address)
    return TokenDiscountResponse(
        wallet_address=wallet_address,
        discounted=info["discounted"],
        tokens_held=info["tokens_held"],
        discount_rate=info["discount_rate"],
        threshold=info["threshold"],
        qualifying_token=info["qualifying_token"],
    )
