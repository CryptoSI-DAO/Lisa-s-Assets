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
import logging
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Optional

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


async def _run_one(canonical: str, netuid: int) -> tuple[str, dict[str, Any]]:
    """Run a single agent, returning (canonical_name, score_dict)."""
    agent = _load_agent(canonical)
    if agent is None:
        return canonical, {"total": 5.0, "notes": ["agent unavailable"]}

    try:
        if hasattr(agent, "score_async"):
            result = await agent.score_async(netuid)
        elif hasattr(agent, "_score_async"):
            result = await agent._score_async(netuid)
        elif hasattr(agent, "score"):
            result = await asyncio.to_thread(agent.score, netuid)
        else:
            return canonical, {"total": 5.0, "notes": ["no score method"]}
    except Exception as exc:
        logger.warning("Agent %s failed for netuid=%s: %s", canonical, netuid, exc)
        return canonical, {"total": 5.0, "notes": [f"error: {exc}"]}

    return canonical, _score_to_dict(result)


async def run_all_agents(netuid: int) -> dict[str, Any]:
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

    tasks = [_run_one(name, netuid) for name in CANONICAL_WEIGHTS]
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
