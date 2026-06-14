"""Agent runner — bridges the existing ``agents/`` package into the backend.

The repository ships 7 scoring agents under ``agents/`` (EmissionMetrics,
SubnetOracle, StakeFlow, SubnetEconomics, HypePulse, CodeCrafter, RiskEye).
Each agent exposes a ``score(netuid)`` (or ``score_async``) method returning a
dataclass with a ``total`` field in the 1–10 range.

This module:
  * Loads the agents package from the repo root (the parent of ``backend/``).
  * Runs every agent against a given target and synthesises the Lisa
    Coefficient using the canonical weights.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import re
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

from .. import db

logger = logging.getLogger(__name__)

# Canonical agent weights (must match eval.py / published scorecards)
CANONICAL_WEIGHTS: dict[str, float] = {
    "truthSeeker": 0.20,
    "mavenMetrics": 0.20,
    "tokenLogic": 0.15,
    "liquidEdge": 0.15,
    "hypePulse": 0.10,
    "codeCrafter": 0.10,
    "riskEye": 0.10,
}

# Map canonical agent name -> (module attr name, class name) inside agents/
_AGENT_MAP: dict[str, tuple[str, str]] = {
    "truthSeeker":  ("subnet_oracle",    "SubnetOracleAgent"),
    "mavenMetrics": ("emission_metrics", "EmissionMetricsAgent"),
    "tokenLogic":   ("subnet_economics", "SubnetEconomicsAgent"),
    "liquidEdge":   ("stake_flow",       "StakeFlowAgent"),
    "hypePulse":    ("hype_pulse",       "HypePulseAgent"),
    "codeCrafter":  ("code_crafter",     "CodeCrafterAgent"),
    "riskEye":      ("risk_eye",         "RiskEyeAgent"),
}


def _ensure_agents_importable() -> None:
    """Add the repo root to sys.path so ``import agents`` works."""
    # backend/app/services/agent_runner.py → repo root is 3 parents up
    repo_root = Path(__file__).resolve().parents[3]
    root_str = str(repo_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def _load_agent(canonical: str) -> Optional[Any]:
    """Instantiate one agent by canonical name. Returns None on failure."""
    module_name, class_name = _AGENT_MAP[canonical]
    try:
        mod = importlib.import_module(f"agents.{module_name}")
        cls = getattr(mod, class_name)
        return cls()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not load agent %s (%s): %s", canonical, class_name, exc)
        return None


def _score_to_dict(result: Any) -> dict[str, Any]:
    """Normalise an agent result (dataclass or dict) into a JSON-safe dict."""
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if isinstance(result, dict):
        return result
    # Fallback: best-effort __dict__
    if hasattr(result, "__dict__"):
        return {k: v for k, v in vars(result).items() if not k.startswith("_")}
    try:
        return {"total": float(result) if result is not None else 5.0}  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {"total": 5.0}


async def _run_one(canonical: str, netuid: int,
                   graceful: bool = False) -> tuple[str, dict[str, Any]]:
    """Run a single agent, returning (canonical_name, score_dict).

    With ``graceful=False`` (default) a failing agent yields a neutral 5.0
    score with an explanatory note — the original behaviour.

    With ``graceful=True`` a failing agent yields ``{"total": None, ...}`` so
    the caller can distinguish "agent ran" from "agent could not score this
    project". This is what :func:`run_full_report` uses for non-Bittensor
    projects where some agents have nothing to evaluate.
    """
    agent = _load_agent(canonical)
    fallback = 5.0 if not graceful else None
    if agent is None:
        return canonical, {"total": fallback, "notes": ["agent unavailable"]}

    try:
        if hasattr(agent, "score_async"):
            result = await agent.score_async(netuid)
        elif hasattr(agent, "_score_async"):
            result = await agent._score_async(netuid)
        elif hasattr(agent, "score"):
            result = await asyncio.to_thread(agent.score, netuid)
        else:
            return canonical, {"total": fallback, "notes": ["no score method"]}
    except Exception as exc:
        logger.warning("Agent %s failed for netuid=%s: %s", canonical, netuid, exc)
        return canonical, {
            "total": fallback,
            "notes": [f"agent error: {exc.__class__.__name__}: {exc}"],
        }

    return canonical, _score_to_dict(result)


async def run_all_agents(netuid: int, *, graceful: bool = False) -> dict[str, Any]:
    """Run every canonical agent against ``netuid`` and return a payload.

    Returns:
        {
          "agent_scores": {canonical: {total, ...}},
          "lisa_coefficient": float,
          "lisa_verdict": str,
          "strongest_agent": str,
        }
    """
    _ensure_agents_importable()

    tasks = [_run_one(name, netuid, graceful=graceful) for name in CANONICAL_WEIGHTS]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    agent_scores = {name: payload for name, payload in results}

    coefficient, strongest = compute_coefficient(agent_scores)
    verdict = verdict_from_coefficient(coefficient)

    return {
        "agent_scores": agent_scores,
        "lisa_coefficient": coefficient,
        "lisa_verdict": verdict,
        "strongest_agent": strongest,
    }


def compute_coefficient(agent_scores: dict[str, Any]) -> tuple[float, str]:
    """Weighted-average Lisa Coefficient from agent scores + strongest agent."""
    total = 0.0
    strongest_name = ""
    strongest_score = -1.0
    for name, weight in CANONICAL_WEIGHTS.items():
        payload = agent_scores.get(name) or {}
        score = payload.get("total", 5.0) if isinstance(payload, dict) else 5.0
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 5.0
        score = max(1.0, min(10.0, score))
        total += score * weight
        if score > strongest_score:
            strongest_score = score
            strongest_name = name
    return round(total, 2), strongest_name


def verdict_from_coefficient(coefficient: float) -> str:
    """Human-readable verdict bucket for a coefficient in [1, 10]."""
    if coefficient >= 8.5:
        return "Alpha 🔥"
    if coefficient >= 7.0:
        return "Strong Buy"
    if coefficient >= 5.5:
        return "Accumulate"
    if coefficient >= 4.0:
        return "Watch"
    if coefficient >= 2.5:
        return "Caution"
    return "Avoid"


# ===========================================================================
# Full report pipeline (Issue #5)
# ===========================================================================
_REPORT_CACHE_DAYS = 30


def _guess_netuid(coingecko_id: str) -> Optional[int]:
    """Best-effort derivation of a Bittensor netuid from a project identifier.

    The specialist agents are built for Bittensor subnets and keyed by netuid
    (an int). Many tracked projects are *not* Bittensor subnets — for those we
    return ``None`` and the agents are run with graceful null-score fallback.
    """
    if not coingecko_id:
        return None
    # Common CoinGecko id patterns: "bittensor-subnet-80", "tao-subnet-92".
    m = re.search(r"subnet[-_ ]?(\d{1,3})\b", coingecko_id, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 0 <= n <= 200:
            return n
    # Pure numeric ids.
    if coingecko_id.isdigit():
        n = int(coingecko_id)
        if 0 <= n <= 200:
            return n
    return None


async def _ensure_project(coingecko_id: str) -> dict[str, Any]:
    """Look up a project by coingecko_id; create it from CoinGecko if missing.

    Returns ``{id, coingecko_id, name, symbol, logo_url}``.
    """
    row = await db.fetchrow(
        "SELECT id, coingecko_id, name, symbol, logo_url FROM projects "
        "WHERE coingecko_id = $1",
        coingecko_id,
    )
    if row is not None:
        return dict(row)

    # Fetch from CoinGecko and persist.
    from . import coingecko as cg
    info = await cg.get_project(coingecko_id)
    name = (info.get("name") or coingecko_id).strip() or coingecko_id
    symbol = (info.get("symbol") or "").strip().upper() or "N/A"
    logo = info.get("logo")

    row = await db.fetchrow(
        """
        INSERT INTO projects (coingecko_id, name, symbol, logo_url)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (coingecko_id) DO UPDATE
          SET name = EXCLUDED.name,
              symbol = EXCLUDED.symbol,
              logo_url = EXCLUDED.logo_url
        RETURNING id, coingecko_id, name, symbol, logo_url
        """,
        coingecko_id, name, symbol, logo,
    )
    return dict(row)


async def _fetch_previous_reports(project_id: str) -> list[dict[str, Any]]:
    """Fetch historical reports (for Lisa Kim's trajectory analysis)."""
    rows = await db.fetch(
        """
        SELECT lisa_coefficient, created_at
        FROM reports
        WHERE project_id = $1
          AND status IN ('public', 'published', 'completed')
          AND lisa_coefficient IS NOT NULL
        ORDER BY created_at ASC
        """,
        project_id,
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        created = r["created_at"]
        out.append({
            "score": float(r["lisa_coefficient"]),
            "coefficient": float(r["lisa_coefficient"]),
            "date": created.isoformat() if created else None,
        })
    return out


async def _recent_report(project_id: str) -> Optional[dict[str, Any]]:
    """Return the most recent public report if it is within the cache window."""
    row = await db.fetchrow(
        """
        SELECT id, lisa_coefficient, lisa_verdict, agent_scores,
               strongest_agent, status, paid_by_wallet, created_at, expires_at
        FROM reports
        WHERE project_id = $1
          AND status IN ('public', 'published', 'completed')
          AND created_at > NOW() - INTERVAL '%s days'
        ORDER BY created_at DESC
        LIMIT 1
        """ % _REPORT_CACHE_DAYS,
        project_id,
    )
    if row is None:
        return None
    return dict(row)


async def run_full_report(
    coingecko_id: str,
    *,
    netuid: Optional[int] = None,
    force_refresh: bool = False,
    paid_by_wallet: Optional[str] = None,
    report_id: Optional[str] = None,
) -> dict[str, Any]:
    """End-to-end report generation for a project.

    Steps:
      1. Resolve/create the project row.
      2. Return a cached report (<30 days) unless ``force_refresh``.
      3. Run all 7 specialist agents (graceful: failures → null scores).
      4. Synthesise the Lisa Coefficient via LisaKimAgent (with history).
      5. Insert (or update, when ``report_id`` is given) the report row.

    Returns the full report as a dict.
    """
    _ensure_agents_importable()

    project = await _ensure_project(coingecko_id)
    project_id = str(project["id"])

    # Cached report?
    if not force_refresh and report_id is None:
        cached = await _recent_report(project_id)
        if cached:
            cached.update({
                "coingecko_id": coingecko_id,
                "project_id": project_id,
                "name": project.get("name"),
                "cached": True,
            })
            return _serialise_report(cached)

    # Pick a netuid (explicit > guessed > 0 sentinel).
    if netuid is None:
        netuid = _guess_netuid(coingecko_id)
    if netuid is None:
        # No subnet mapping — run with a sentinel so agents at least try.
        # Specialists without data for netuid 0 will mostly return low scores
        # or fail gracefully; either is acceptable for non-Bittensor projects.
        netuid = 0
        logger.info("No netuid mapping for %s; running agents with sentinel 0",
                    coingecko_id)

    # Run specialist agents.
    payload = await run_all_agents(netuid, graceful=True)
    agent_scores: dict[str, Any] = payload["agent_scores"]

    # Build flat {agent: score} for the meta-agent (Lisa Kim handles missing
    # values by defaulting to 5.0).
    flat_scores: dict[str, float] = {}
    for name, data in agent_scores.items():
        total = data.get("total") if isinstance(data, dict) else data
        if total is not None:
            try:
                flat_scores[name] = float(total)
            except (TypeError, ValueError):
                pass

    # Synthesise via Lisa Kim.
    previous_reports = await _fetch_previous_reports(project_id)
    lisa_result = await _run_lisa_kim(flat_scores, previous_reports)

    coefficient = float(lisa_result.get("total", payload["lisa_coefficient"]))
    verdict = lisa_result.get("verdict") or payload["lisa_verdict"]
    strongest = payload["strongest_agent"]

    # Enrich the stored agent_scores with Lisa Kim's synthesis + trajectory.
    agent_scores_out = {
        **agent_scores,
        "_meta": {
            "lisa_coefficient": coefficient,
            "verdict": verdict,
            "trajectory": lisa_result.get("trajectory"),
            "notes": lisa_result.get("notes", []),
            "details": lisa_result.get("details", {}),
            "netuid_used": netuid,
            "agents_failed": [
                n for n, d in agent_scores.items()
                if isinstance(d, dict) and d.get("total") is None
            ],
        },
    }

    scores_json = json.dumps(agent_scores_out)

    row = None
    if report_id:
        # Update a pre-created (e.g. "queued") row.
        row = await db.fetchrow(
            """
            UPDATE reports SET
                lisa_coefficient = $2,
                lisa_verdict     = $3,
                agent_scores     = $4::jsonb,
                strongest_agent  = $5,
                status           = 'public'
            WHERE id::text = $1
            RETURNING id, created_at, expires_at, status
            """,
            report_id, coefficient, verdict, scores_json, strongest,
        )

    if row is None:
        # Either no report_id was provided, or the queued row vanished —
        # insert a fresh public report.
        row = await db.fetchrow(
            """
            INSERT INTO reports
                (project_id, lisa_coefficient, lisa_verdict, agent_scores,
                 strongest_agent, status, paid_by_wallet)
            VALUES ($1, $2, $3, $4::jsonb, $5, 'public', $6)
            RETURNING id, created_at, expires_at, status
            """,
            project_id, coefficient, verdict, scores_json, strongest,
            paid_by_wallet,
        )

    report = {
        "id": str(row["id"]),
        "coingecko_id": coingecko_id,
        "project_id": project_id,
        "name": project.get("name"),
        "symbol": project.get("symbol"),
        "lisa_coefficient": coefficient,
        "lisa_verdict": verdict,
        "strongest_agent": strongest,
        "agent_scores": agent_scores_out,
        "status": row["status"],
        "paid_by_wallet": paid_by_wallet,
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "cached": False,
    }
    return _serialise_report(report)


async def _run_lisa_kim(flat_scores: dict[str, float],
                        previous_reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Invoke LisaKimAgent.analyze defensively; fall back to weighted average."""
    try:
        from agents.lisa_kim import LisaKimAgent
        agent = LisaKimAgent()
        result = await agent.analyze(flat_scores, previous_reports)
        return {
            "total": result.total,
            "verdict": result.verdict,
            "notes": list(result.notes or []),
            "trajectory": result.trajectory,
            "details": result.details or {},
        }
    except Exception as exc:
        logger.warning("LisaKimAgent failed, using fallback coefficient: %s", exc)
        coeff, _ = compute_coefficient({k: {"total": v} for k, v in flat_scores.items()})
        return {
            "total": coeff,
            "verdict": verdict_from_coefficient(coeff),
            "notes": [f"Lisa Kim meta-agent unavailable: {exc}"],
            "trajectory": None,
            "details": {"fallback": True},
        }


def _serialise_report(report: dict[str, Any]) -> dict[str, Any]:
    """Make a report dict JSON-safe (timestamps → ISO strings)."""
    for key in ("created_at", "expires_at"):
        val = report.get(key)
        if val is not None and not isinstance(val, str):
            report[key] = val.isoformat()
    return report
