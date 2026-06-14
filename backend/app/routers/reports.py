"""Reports router — read reports and request new ones.

Issue #1 / #4.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from .. import db
from ..models.schemas import ReportFull, ReportRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


@router.get("/api/reports/{report_id}", response_model=ReportFull,
            summary="Fetch a full report by id")
async def get_report(report_id: str):
    """Return a single report including its agent_scores breakdown."""
    row = await db.fetchrow(
        """
        SELECT r.id, r.project_id, r.lisa_coefficient, r.lisa_verdict,
               r.agent_scores, r.strongest_agent, r.status, r.paid_by_wallet,
               r.crowdfund_pool_id, r.created_at, r.expires_at,
               p.coingecko_id
        FROM reports r
        LEFT JOIN projects p ON p.id = r.project_id
        WHERE r.id::text = $1
        """,
        report_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")

    # Respect visibility: only public reports are world-readable via the API.
    status = (row["status"] or "").lower()
    if status not in ("public", "published", "completed"):
        raise HTTPException(
            status_code=402,
            detail=(
                f"Report '{report_id}' is not publicly available "
                f"(status='{row['status']}'). Payment required."
            ),
        )

    return ReportFull(
        id=str(row["id"]),
        project_id=str(row["project_id"]) if row["project_id"] else None,
        lisa_coefficient=float(row["lisa_coefficient"]),
        lisa_verdict=row["lisa_verdict"],
        strongest_agent=row["strongest_agent"],
        status=row["status"],
        agent_scores=row["agent_scores"] or {},
        paid_by_wallet=row["paid_by_wallet"],
        crowdfund_pool_id=str(row["crowdfund_pool_id"]) if row["crowdfund_pool_id"] else None,
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


@router.post("/api/projects/{coingecko_id}/report",
             status_code=501,
             summary="Request a new report (stub — payment required)")
async def request_report(coingecko_id: str, body: ReportRequest):
    """Request generation of a fresh Lisa Coefficient report.

    **Stub.** Real report generation is gated behind payment verification
    (issue #6). Until then this endpoint always returns **501** with the
    payload the *real* endpoint would accept, so the frontend can be wired up
    against a stable contract.
    """
    # Confirm the project exists so callers get a 404 for unknown projects.
    row = await db.fetchrow(
        "SELECT id, name FROM projects WHERE coingecko_id = $1", coingecko_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Project '{coingecko_id}' not found")

    return {
        "detail": "Report generation requires payment — endpoint is a stub.",
        "coingecko_id": coingecko_id,
        "project": row["name"],
        "status": "not_implemented",
        "next_step": "POST /api/payments/checkout to obtain a payment address, "
                     "then POST /api/payments/verify once the tx is confirmed.",
        "request_echo": body.model_dump(),
    }
