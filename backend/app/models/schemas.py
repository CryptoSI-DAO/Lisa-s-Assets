"""Pydantic v2 request/response schemas for the Lisa's Assets API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class ProjectSummary(BaseModel):
    id: str
    coingecko_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    latest_coefficient: Optional[float] = None
    latest_verdict: Optional[str] = None
    report_count: int = 0


class ProjectDetail(BaseModel):
    id: str
    coingecko_id: str
    name: str
    symbol: str
    logo_url: Optional[str] = None
    price_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    description: Optional[str] = None
    latest_report: Optional["ReportSummary"] = None


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
    page: int
    limit: int
    pages: int


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class AgentScore(BaseModel):
    total: float = Field(..., description="Agent's 1-10 score")
    notes: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ReportSummary(BaseModel):
    id: str
    project_id: Optional[str] = None
    lisa_coefficient: float
    lisa_verdict: Optional[str] = None
    strongest_agent: Optional[str] = None
    status: str = "generating"
    created_at: datetime


class ReportFull(ReportSummary):
    agent_scores: dict[str, Any]
    paid_by_wallet: Optional[str] = None
    crowdfund_pool_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class ReportRequest(BaseModel):
    """Request body for POST /api/projects/{coingecko_id}/report."""
    wallet_address: Optional[str] = None
    crowdfund_pool_id: Optional[str] = None
    force_refresh: bool = False


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class CheckoutRequest(BaseModel):
    report_id: Optional[str] = None
    coingecko_id: Optional[str] = None
    wallet_address: str
    amount: float
    token: str = "USDC"
    chain: str = "base"
    discount_code: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_id: str
    wallet_address: str
    amount: float
    token: str
    chain: str
    expires_at: datetime
    status: str = "awaiting_payment"


class VerifyRequest(BaseModel):
    tx_hash: str
    wallet_address: str
    amount: float
    token: str
    chain: str


class VerifyResponse(BaseModel):
    verified: bool
    tx_hash: str
    message: str


# ---------------------------------------------------------------------------
# Newsletter
# ---------------------------------------------------------------------------
class NewsletterSubscribe(BaseModel):
    email: EmailStr
    wallet_address: Optional[str] = None
    tier: str = "free"


class NewsletterResponse(BaseModel):
    subscribed: bool
    email: str
    tier: str
    message: str


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    database: str = "unknown"


class ErrorResponse(BaseModel):
    detail: str


# Forward-ref resolution
ProjectDetail.model_rebuild()
