"""Projects router — browse, search and inspect tracked crypto projects.

Issue #1 / #4.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..models.schemas import ProjectDetail, ProjectListResponse, ProjectSummary
from ..services import coingecko

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _record_to_summary(row) -> ProjectSummary:
    """Map a joined projects/latest-report row to a ProjectSummary."""
    return ProjectSummary(
        id=str(row["id"]),
        coingecko_id=row["coingecko_id"],
        name=row["name"],
        symbol=row["symbol"],
        logo_url=row.get("logo_url"),
        latest_coefficient=_f(row.get("latest_coefficient")),
        latest_verdict=row.get("latest_verdict"),
        report_count=int(row.get("report_count") or 0),
    )


def _f(val):
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


@router.get("", response_model=ProjectListResponse, summary="List & search projects")
async def list_projects(
    search: Optional[str] = Query(None, description="Substring search on name/symbol"),
    sort: str = Query("recent", pattern="^(coefficient|recent|alpha)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """Paginated list of projects, optionally joined with the latest report.

    `sort`:
      * `coefficient` — highest Lisa Coefficient first
      * `recent`      — most recently reported
      * `alpha`       — highest strongest-agent score
    """
    offset = (page - 1) * limit

    order_clause = {
        "coefficient": "latest_coefficient DESC NULLS LAST",
        "alpha": "latest_coefficient DESC NULLS LAST",
        "recent": "latest_created_at DESC NULLS LAST, p.created_at DESC",
    }[sort]

    where = ""
    params: list = []
    if search:
        where = "WHERE p.name ILIKE $1 OR p.symbol ILIKE $1 OR p.coingecko_id ILIKE $1"
        params.append(f"%{search}%")

    # Count
    count_sql = f"SELECT COUNT(*) FROM projects p {where}"
    total = await db.fetchval(count_sql, *params) if params else await db.fetchval(count_sql)
    total = int(total or 0)

    # pkey index offset for pagination params (search uses $1)
    if params:
        page_params = [*params, limit, offset]
        limit_ph, offset_ph = "$2", "$3"
    else:
        page_params = [limit, offset]
        limit_ph, offset_ph = "$1", "$2"

    rows = await db.fetch(
        f"""
        SELECT
            p.id, p.coingecko_id, p.name, p.symbol, p.logo_url, p.created_at,
            (SELECT r.lisa_coefficient FROM reports r
              WHERE r.project_id = p.id
              ORDER BY r.created_at DESC LIMIT 1) AS latest_coefficient,
            (SELECT r.lisa_verdict FROM reports r
              WHERE r.project_id = p.id
              ORDER BY r.created_at DESC LIMIT 1) AS latest_verdict,
            (SELECT r.created_at FROM reports r
              WHERE r.project_id = p.id
              ORDER BY r.created_at DESC LIMIT 1) AS latest_created_at,
            (SELECT COUNT(*) FROM reports r WHERE r.project_id = p.id) AS report_count
        FROM projects p
        {where}
        ORDER BY {order_clause}
        LIMIT {limit_ph} OFFSET {offset_ph}
        """,
        *page_params,
    )

    items = [_record_to_summary(r) for r in rows]
    pages = (total + limit - 1) // limit if total else 0
    return ProjectListResponse(
        items=items, total=total, page=page, limit=limit, pages=pages
    )


@router.get("/search", summary="Search projects via CoinGecko")
async def search_projects_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
):
    """Live CoinGecko search (not limited to projects already in the DB)."""
    results = await coingecko.search_projects(q)
    return {"query": q, "count": len(results), "results": results}


@router.get("/top", summary="Top projects by market cap")
async def top_projects_endpoint(
    limit: int = Query(50, ge=1, le=250),
):
    """Top projects by market cap, sourced live from CoinGecko."""
    results = await coingecko.get_top_projects(limit)
    return {"count": len(results), "results": results}


@router.get("/{coingecko_id}", response_model=ProjectDetail,
            summary="Project detail + latest public report")
async def get_project_detail(coingecko_id: str):
    """Return a single project, enriched with live CoinGecko data and its
    latest public report (if any)."""
    row = await db.fetchrow(
        """
        SELECT p.id, p.coingecko_id, p.name, p.symbol, p.logo_url
        FROM projects p
        WHERE p.coingecko_id = $1
        """,
        coingecko_id,
    )

    if row is None:
        raise HTTPException(status_code=404, detail=f"Project '{coingecko_id}' not found")

    # Live CoinGecko enrichment (best-effort; never 500 on API failure)
    price_usd = market_cap_usd = description = logo = None
    try:
        cg = await coingecko.get_project(coingecko_id)
        price_usd = cg.get("price_usd")
        market_cap_usd = cg.get("market_cap_usd")
        description = cg.get("description")
        logo = cg.get("logo")
    except Exception as exc:
        logger.warning("CoinGecko enrichment failed for %s: %s", coingecko_id, exc)

    # Latest public report
    report_row = await db.fetchrow(
        """
        SELECT id, project_id, lisa_coefficient, lisa_verdict, strongest_agent,
               status, created_at
        FROM reports
        WHERE project_id = $1 AND status IN ('public', 'published', 'completed')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        row["id"],
    )

    latest_report = None
    if report_row is not None:
        from ..models.schemas import ReportSummary
        latest_report = ReportSummary(
            id=str(report_row["id"]),
            project_id=str(report_row["project_id"]) if report_row["project_id"] else None,
            lisa_coefficient=float(report_row["lisa_coefficient"]),
            lisa_verdict=report_row["lisa_verdict"],
            strongest_agent=report_row["strongest_agent"],
            status=report_row["status"],
            created_at=report_row["created_at"],
        )

    return ProjectDetail(
        id=str(row["id"]),
        coingecko_id=row["coingecko_id"],
        name=row["name"],
        symbol=row["symbol"],
        logo_url=logo or row["logo_url"],
        price_usd=price_usd,
        market_cap_usd=market_cap_usd,
        description=description,
        latest_report=latest_report,
    )


@router.get("/{coingecko_id}/history", summary="All reports for a project")
async def project_history(coingecko_id: str):
    """Chronological list of all reports for a project."""
    row = await db.fetchrow(
        "SELECT id FROM projects WHERE coingecko_id = $1", coingecko_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Project '{coingecko_id}' not found")

    reports = await db.fetch(
        """
        SELECT id, lisa_coefficient, lisa_verdict, strongest_agent, status,
               paid_by_wallet, created_at
        FROM reports
        WHERE project_id = $1
        ORDER BY created_at ASC
        """,
        row["id"],
    )
    return {
        "coingecko_id": coingecko_id,
        "count": len(reports),
        "history": [
            {
                "id": str(r["id"]),
                "lisa_coefficient": float(r["lisa_coefficient"]),
                "lisa_verdict": r["lisa_verdict"],
                "strongest_agent": r["strongest_agent"],
                "status": r["status"],
                "paid_by_wallet": r["paid_by_wallet"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in reports
        ],
    }
