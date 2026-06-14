"""Reports router — read reports, request new ones, poll generation status.

Issues #1 / #4 / #6.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from .. import db
from ..config import get_settings
from ..models.schemas import ReportFull, ReportRequest
from ..services import payment
from ..services.agent_runner import run_full_report

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _has_verified_payment(wallet_address: str) -> bool:
    """Return True if ``wallet_address`` has at least one verified payment row."""
    if not wallet_address:
        return False
    val = await db.fetchval(
        "SELECT 1 FROM payments "
        "WHERE wallet_address = $1 AND verified = TRUE LIMIT 1",
        wallet_address,
    )
    return val is not None


def _payment_required_response(coingecko_id: str, wallet_address: str | None):
    """Build the 402 payload describing how to pay."""
    price = payment.compute_price(wallet_address)
    return {
        "detail": "Payment required to generate a report.",
        "coingecko_id": coingecko_id,
        "status": "payment_required",
        "price": price,
        "instructions": (
            f"Send {price['amount']} USDC on Base to "
            f"{get_settings().PAYMENT_RECEIVE_ADDRESS}, then POST "
            f"/api/payments/verify with the tx hash, then retry this endpoint."
        ),
        "next_step": "POST /api/payments/checkout → /api/payments/verify → retry",
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
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


class ReportAccepted(BaseModel):
    """Response for an accepted (async) report request."""
    report_id: str
    coingecko_id: str
    status: str
    cached: bool = False
    message: str = ""


@router.post("/api/projects/{coingecko_id}/report",
             response_model=ReportAccepted,
             summary="Request a new report (payment-gated)")
async def request_report(
    coingecko_id: str,
    body: ReportRequest,
    background_tasks: BackgroundTasks,
):
    """Request generation of a fresh Lisa Coefficient report.

    Payment policy (MVP):
      * If ``PAYMENT_REQUIRED`` is False (default), generation runs without a
        verified payment — useful for demo/open access.
      * If ``PAYMENT_REQUIRED`` is True, a ``wallet_address`` with a verified
        payment row is required; otherwise a 402 is returned.

    Generation runs asynchronously via FastAPI ``BackgroundTasks``. The
    endpoint returns immediately with a ``report_id`` and ``status='queued'``;
    poll ``GET /api/projects/{coingecko_id}/report/status`` to know when the
    report is ready.
    """
    settings = get_settings()

    # ── Payment gating ─────────────────────────────────────────────────────
    wallet = body.wallet_address
    if settings.PAYMENT_REQUIRED:
        if not wallet or not await _has_verified_payment(wallet):
            raise HTTPException(
                status_code=402,
                detail=_payment_required_response(coingecko_id, wallet),
            )

    # ── Ensure the project exists (so we can attach the queued report) ─────
    project = await db.fetchrow(
        "SELECT id, name FROM projects WHERE coingecko_id = $1", coingecko_id
    )
    # If the project isn't tracked yet, create a placeholder row; the full
    # project metadata (name/symbol/logo) is filled in by run_full_report via
    # CoinGecko.
    project_id = str(project["id"]) if project else None
    if project_id is None:
        project_id = await db.fetchval(
            """
            INSERT INTO projects (coingecko_id, name, symbol)
            VALUES ($1, $1, 'N/A')
            ON CONFLICT (coingecko_id) DO UPDATE SET coingecko_id = EXCLUDED.coingecko_id
            RETURNING id::text
            """,
            coingecko_id,
        )

    # ── Create a "queued" report row and return its id immediately ─────────
    report_id = await db.fetchval(
        """
        INSERT INTO reports
            (project_id, lisa_coefficient, lisa_verdict, agent_scores,
             strongest_agent, status, paid_by_wallet)
        VALUES ($1, 0.0, 'queued', '{}'::jsonb, NULL, 'queued', $2)
        RETURNING id::text
        """,
        project_id, wallet,
    )

    # ── Kick off generation in the background ──────────────────────────────
    async def _generate():
        try:
            await run_full_report(
                coingecko_id,
                force_refresh=body.force_refresh,
                paid_by_wallet=wallet,
                report_id=report_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Background report generation failed for %s: %s",
                             coingecko_id, exc)
            try:
                await db.execute(
                    "UPDATE reports SET status = 'failed', "
                    "lisa_verdict = 'generation failed' WHERE id::text = $1",
                    report_id,
                )
            except Exception:
                pass

    background_tasks.add_task(_generate)

    return ReportAccepted(
        report_id=report_id,
        coingecko_id=coingecko_id,
        status="queued",
        cached=False,
        message="Report generation queued. Poll the status endpoint.",
    )


@router.get("/api/projects/{coingecko_id}/report/status",
            summary="Latest report status for a project")
async def report_status(coingecko_id: str):
    """Return the most recent report (any status) for a project.

    Useful for polling after a POST to the report endpoint: once ``status``
    flips to ``public`` the report is ready to read.
    """
    row = await db.fetchrow(
        """
        SELECT r.id, r.status, r.lisa_coefficient, r.lisa_verdict,
               r.strongest_agent, r.paid_by_wallet, r.created_at, r.expires_at
        FROM reports r
        JOIN projects p ON p.id = r.project_id
        WHERE p.coingecko_id = $1
        ORDER BY r.created_at DESC
        LIMIT 1
        """,
        coingecko_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for project '{coingecko_id}'",
        )

    def _iso(val):
        return val.isoformat() if isinstance(val, datetime) else val

    return {
        "report_id": str(row["id"]),
        "coingecko_id": coingecko_id,
        "status": row["status"],
        "lisa_coefficient": (
            float(row["lisa_coefficient"]) if row["lisa_coefficient"] is not None else None
        ),
        "lisa_verdict": row["lisa_verdict"],
        "strongest_agent": row["strongest_agent"],
        "paid_by_wallet": row["paid_by_wallet"],
        "created_at": _iso(row["created_at"]),
        "expires_at": _iso(row["expires_at"]),
        "is_ready": (row["status"] or "").lower() in ("public", "published", "completed"),
    }
