"""NFT export router — SVG agent cards + ERC-721-style metadata.

Endpoints:
  GET /api/reports/{report_id}/nft-card      → SVG image (strongest agent)
  GET /api/reports/{report_id}/nft-metadata  → JSON metadata (ERC-721 style)
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .. import db
from ..services.nft_card import generate_agent_card_svg, resolve_agent_meta, today_str

logger = logging.getLogger(__name__)

router = APIRouter(tags=["nft"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _load_report(report_id: str) -> dict:
    """Fetch a report + its project info for NFT export.

    Returns a dict with: id, project_name, project_symbol, coefficient,
    verdict, strongest_agent, created_at.
    """
    row = await db.fetchrow(
        """
        SELECT r.id, r.lisa_coefficient, r.lisa_verdict,
               r.strongest_agent, r.status, r.created_at,
               p.name  AS project_name,
               p.symbol AS project_symbol
        FROM reports r
        LEFT JOIN projects p ON p.id = r.project_id
        WHERE r.id::text = $1
        """,
        report_id,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_id}' not found",
        )
    return dict(row)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get(
    "/api/reports/{report_id}/nft-card",
    summary="NFT agent card (SVG)",
    response_class=Response,
)
async def get_nft_card(report_id: str):
    """Return an SVG image of the strongest agent's card for this report."""
    # Allow a quick smoke-test without a DB row.
    if report_id == "test":
        svg = generate_agent_card_svg(
            agent_name="HypePulse",
            agent_emoji="🔥",
            project_name="Lido",
            project_symbol="LDO",
            coefficient=8.4,
            verdict="Strong Buy",
            date_str=today_str(),
            strongest=True,
        )
        return Response(content=svg, media_type="image/svg+xml")

    report = await _load_report(report_id)

    strongest_key = report.get("strongest_agent") or ""
    meta = resolve_agent_meta(strongest_key)

    created = report.get("created_at")
    if isinstance(created, datetime):
        date_str = created.strftime("%Y-%m-%d")
    elif created:
        date_str = str(created)[:10]
    else:
        date_str = today_str()

    coeff = float(report.get("lisa_coefficient") or 5.0)
    verdict = report.get("lisa_verdict") or "—"

    svg = generate_agent_card_svg(
        agent_name=meta["name"],
        agent_emoji=meta["emoji"],
        project_name=report.get("project_name") or "Unknown",
        project_symbol=report.get("project_symbol") or "???",
        coefficient=coeff,
        verdict=verdict,
        date_str=date_str,
        strongest=True,
    )
    return Response(content=svg, media_type="image/svg+xml")


@router.get(
    "/api/reports/{report_id}/nft-metadata",
    summary="NFT metadata (ERC-721 style)",
)
async def get_nft_metadata(report_id: str):
    """Return ERC-721-style JSON metadata for minting an NFT from a report."""
    # Quick smoke-test variant.
    if report_id == "test":
        return {
            "name": "Lisa's Assets: LDO Report",
            "description": "Lisa Coefficient: 8.4 - Strong fundamentals detected across multiple agent dimensions.",
            "image": f"/api/reports/{report_id}/nft-card",
            "attributes": [
                {"trait_type": "Project", "value": "Lido"},
                {"trait_type": "Symbol", "value": "LDO"},
                {"trait_type": "Lisa Coefficient", "value": 8.4},
                {"trait_type": "Top Agent", "value": "HypePulse"},
                {"trait_type": "Date", "value": today_str()},
            ],
        }

    report = await _load_report(report_id)

    strongest_key = report.get("strongest_agent") or ""
    meta = resolve_agent_meta(strongest_key)

    coeff = float(report.get("lisa_coefficient") or 0.0)
    project_name = report.get("project_name") or "Unknown"
    project_symbol = report.get("project_symbol") or "???"
    verdict = report.get("lisa_verdict") or ""

    created = report.get("created_at")
    if isinstance(created, datetime):
        date_str = created.strftime("%Y-%m-%d")
    elif created:
        date_str = str(created)[:10]
    else:
        date_str = today_str()

    description = (
        f"Lisa Coefficient: {coeff:.1f} - {verdict}"
        if verdict
        else f"Lisa Coefficient: {coeff:.1f}"
    )

    return {
        "name": f"Lisa's Assets: {project_symbol} Report",
        "description": description,
        "image": f"/api/reports/{report_id}/nft-card",
        "attributes": [
            {"trait_type": "Project", "value": project_name},
            {"trait_type": "Symbol", "value": project_symbol},
            {"trait_type": "Lisa Coefficient", "value": coeff},
            {"trait_type": "Top Agent", "value": meta["name"]},
            {"trait_type": "Date", "value": date_str},
        ],
    }
