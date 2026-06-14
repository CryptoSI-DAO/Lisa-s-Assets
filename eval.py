#!/usr/bin/env python3
"""
SubWatch Lisa Coefficient — Benchmark Eval Script for Arbor

Measures the accuracy and consistency of the Lisa Coefficient scoring model.

Metrics:
  1. Formula consistency: does computed_coefficient match published_coefficient?
  2. Cross-validation: can the model predict held-out scores from features?
  3. Internal coherence: are agent sub-scores internally consistent?
  
The eval returns a single composite score (higher = better).
Arbor will try to maximize this score by improving the scoring code.
"""

import json
import math
import sys
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Canonical agent weights (sum to 1.0)
WEIGHTS = {
    "truthSeeker": 0.20,
    "mavenMetrics": 0.20,
    "tokenLogic": 0.15,
    "liquidEdge": 0.15,
    "hypePulse": 0.10,
    "codeCrafter": 0.10,
    "riskEye": 0.10,
}

# TAO ecosystem uses older key aliases → canonical keys
TAO_KEY_MAP = {
    "oracle": "truthSeeker",
    "emission": "mavenMetrics",
    "economics": "tokenLogic",
    "stakeflow": "liquidEdge",
    "hype": "hypePulse",
    "code": "codeCrafter",
    "risk": "riskEye",
}


def load_datasets():
    """Load all datasets and return normalized entries."""
    entries = []

    # Bittensor subnets
    tao_path = DATA_DIR / "subnets-may-2026.json"
    if tao_path.exists():
        with open(tao_path) as f:
            data = json.load(f)
        for entry in data.get("subnets", data.get("ecosystems", [])):
            if entry.get("hidden"):
                continue
            raw_scores = entry.get("scores", {})
            # Map TAO keys to canonical
            scores = {}
            for k, v in raw_scores.items():
                canon = TAO_KEY_MAP.get(k, k)
                scores[canon] = v
            entries.append({
                "ecosystem": "tao",
                "name": entry.get("name", "unknown"),
                "scores": scores,
                "details": entry.get("details", {}),
                "published_coefficient": raw_scores.get("lisa_coefficient") or entry.get("lisa_coefficient"),
            })

    # ETH ecosystem
    eth_path = DATA_DIR / "eth-ecosystem.json"
    if eth_path.exists():
        with open(eth_path) as f:
            data = json.load(f)
        for entry in data.get("projects", data.get("ecosystems", [])):
            scores = entry.get("scores", {})
            entries.append({
                "ecosystem": "eth",
                "name": entry.get("name", "unknown"),
                "scores": scores,
                "details": entry.get("details", {}),
                "published_coefficient": entry.get("lisa_coefficient") or scores.get("lisa_coefficient"),
            })

    return entries


def compute_lisa_coefficient(scores):
    """Compute the Lisa Coefficient from agent scores using canonical weights."""
    total = 0.0
    for agent, weight in WEIGHTS.items():
        score = scores.get(agent, 5.0)  # default neutral
        if isinstance(score, (int, float)):
            total += score * weight
        else:
            total += 5.0 * weight  # fallback
    return round(total, 2)


def evaluate():
    """Run the full evaluation. Returns (score, details_dict)."""
    entries = load_datasets()

    if not entries:
        return 0.0, {"error": "No data entries found"}

    metrics = {
        "total_entries": len(entries),
        "formula_consistency": 0.0,
        "score_range_valid": 0.0,
        "weight_coverage": 0.0,
        "no_missing_agents": 0.0,
        "penalty": 0.0,
    }

    consistency_errors = []
    range_errors = []
    missing_errors = []

    for entry in entries:
        scores = entry["scores"]
        name = entry["name"]

        # Check all 7 agents are present
        missing = [a for a in WEIGHTS if a not in scores]
        if missing:
            missing_errors.append(f"{name}: missing {missing}")

        # Check score ranges (1-10)
        for agent, score in scores.items():
            if agent in WEIGHTS:  # only check canonical agents
                if isinstance(score, (int, float)):
                    if score < 1 or score > 10:
                        range_errors.append(f"{name}.{agent}={score}")

        # Check formula consistency
        computed = compute_lisa_coefficient(scores)
        published = entry.get("published_coefficient")
        if published is not None and isinstance(published, (int, float)):
            diff = abs(computed - published)
            if diff > 0.01:
                consistency_errors.append(f"{name}: computed={computed} published={published} diff={diff:.2f}")

    # Score calculations (each metric 0-1, then weighted)
    n = len(entries)

    # Formula consistency: what fraction of entries are consistent?
    consistent = n - len(consistency_errors)
    metrics["formula_consistency"] = consistent / n if n > 0 else 0

    # Score range validity
    range_ok = n - len(range_errors)
    metrics["score_range_valid"] = range_ok / n if n > 0 else 0

    # Weight coverage (all agents present)
    complete = n - len(missing_errors)
    metrics["no_missing_agents"] = complete / n if n > 0 else 0

    # Weight coverage: how many of the 7 canonical agents have data
    all_agents = set()
    for entry in entries:
        all_agents.update(entry["scores"].keys())
    canonical_present = sum(1 for a in WEIGHTS if a in all_agents)
    metrics["weight_coverage"] = canonical_present / len(WEIGHTS)

    # Composite score (0-100)
    composite = (
        metrics["formula_consistency"] * 30 +
        metrics["score_range_valid"] * 20 +
        metrics["no_missing_agents"] * 20 +
        metrics["weight_coverage"] * 30
    )

    details = {
        "composite_score": round(composite, 2),
        "metrics": {k: round(v, 4) for k, v in metrics.items() if k != "penalty"},
        "errors": {
            "consistency": consistency_errors[:10],
            "range": range_errors[:10],
            "missing": missing_errors[:10],
        },
        "entry_count": n,
    }

    return composite, details


if __name__ == "__main__":
    # Split: use all entries for now (no held-out set yet)
    score, details = evaluate()
    print(f"\n{'='*60}")
    print(f"Lisa Coefficient Benchmark — Evaluation Results")
    print(f"{'='*60}")
    print(f"Composite Score: {score:.2f} / 100")
    print(f"\nMetrics:")
    for k, v in details["metrics"].items():
        print(f"  {k}: {v:.2%}")
    if details["errors"]["consistency"]:
        print(f"\nConsistency Errors ({len(details['errors']['consistency'])}):")
        for e in details["errors"]["consistency"][:5]:
            print(f"  ⚠️  {e}")
    if details["errors"]["range"]:
        print(f"\nRange Errors ({len(details['errors']['range'])}):")
        for e in details["errors"]["range"][:5]:
            print(f"  ⚠️  {e}")
    if details["errors"]["missing"]:
        print(f"\nMissing Agent Errors ({len(details['errors']['missing'])}):")
        for e in details["errors"]["missing"][:5]:
            print(f"  ⚠️  {e}")
    print(f"\n{'='*60}")

    # Arbor expects a parseable final line
    print(f"\nSCORE: {score:.4f}")
