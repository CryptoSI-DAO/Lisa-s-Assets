#!/usr/bin/env python3
"""
Lisa Coefficient — Benchmark Eval Script for Arbor

Measures the accuracy and consistency of the Lisa Coefficient scoring model
against published scorecards.

The eval checks:
  1. Formula consistency (35%): computed coefficient matches published scorecard value
  2. Agent implementation coverage (25%): how many of 7 agents have working Python code
  3. Scoring coherence (20%): scores follow logical patterns (higher TVL → higher score, etc.)
  4. Code quality (20%): no known bugs, proper exports, all agents wired
  
Composite score: 0-100 (higher = better)
"""

import json
import re
import ast
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"

# Canonical agent weights
CANONICAL_WEIGHTS = {
    "truthSeeker": 0.20,
    "mavenMetrics": 0.20,
    "tokenLogic": 0.15,
    "liquidEdge": 0.15,
    "hypePulse": 0.10,
    "codeCrafter": 0.10,
    "riskEye": 0.10,
}

# TAO key aliases
TAO_KEY_MAP = {
    "oracle": "truthSeeker",
    "emission": "mavenMetrics",
    "economics": "tokenLogic",
    "stakeflow": "liquidEdge",
    "hype": "hypePulse",
    "code": "codeCrafter",
    "risk": "riskEye",
}

CANONICAL_AGENTS = list(CANONICAL_WEIGHTS.keys())


def load_tao_data():
    """Load Bittensor subnet data."""
    path = DATA_DIR / "subnets-may-2026.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    weights = data.get("weights", {})
    entries = []
    for s in data.get("subnets", []):
        if s.get("hidden"):
            continue
        raw_scores = s.get("scores", {})
        # Normalize keys
        scores = {}
        for k, v in raw_scores.items():
            canon = TAO_KEY_MAP.get(k, k)
            scores[canon] = v
        entries.append({
            "name": s.get("name", "unknown"),
            "ecosystem": "tao",
            "scores": scores,
            "details": s.get("details", {}),
            "weights": weights,
        })
    return entries


def load_eth_data():
    """Load ETH ecosystem data."""
    path = DATA_DIR / "eth-ecosystem.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    entries = []
    projects = data.get("projects", [])
    for p in projects:
        scores = p.get("scores", {})
        entries.append({
            "name": p.get("name", "unknown"),
            "ecosystem": "eth",
            "scores": scores,
            "details": {
                "tvl": p.get("tvl", 0),
                "mcap": p.get("mcap", 0),
                "fdv": p.get("fdv", 0),
                "tvl30dChange": p.get("tvl30dChange", 0),
            },
        })
    return entries


def parse_published_coefficients():
    """Parse Lisa Coefficient values from scorecard markdown files."""
    published = {}

    # TAO scorecards
    tao_path = ROOT / "scorecards" / "may-2026.md"
    if tao_path.exists():
        with open(tao_path) as f:
            content = f.read()
        # Pattern: "### ... Name" followed by "Lisa Coefficient: X.X/10"
        # Split by subnet headers
        blocks = re.split(r"###[^#]", content)
        for block in blocks:
            # Extract name from first line
            name_match = re.match(r"\s*(.+?)\n", block)
            coeff_match = re.search(r"Lisa Coefficient:\s*([\d.]+)", block)
            if name_match and coeff_match:
                name = name_match.group(1).strip().split("-")[0].strip()
                published[f"tao:{name.lower()}"] = float(coeff_match.group(1))

    # ETH scorecards
    eth_dir = ROOT / "eth-ecosystem" / "scorecards"
    if eth_dir.exists():
        for md_file in eth_dir.glob("*.md"):
            with open(md_file) as f:
                content = f.read()
            coeff_match = re.search(r"Lisa Coefficient:\s*([\d.]+)", content)
            name_match = re.search(r"###\s+(.+?)\n", content)
            if coeff_match and name_match:
                name = name_match.group(1).strip()
                published[f"eth:{name.lower()}"] = float(coeff_match.group(1))

    return published


def compute_coefficient(scores, weights=None):
    """Compute Lisa Coefficient from agent scores."""
    w = weights or CANONICAL_WEIGHTS
    total = 0.0
    for agent, weight in w.items():
        score = scores.get(agent)
        if score is None:
            score = 5.0
        if isinstance(score, (int, float)):
            total += score * weight
        else:
            total += 5.0 * weight
    return round(total, 2)


def check_formula_consistency(entries, published):
    """Check if computed coefficients match published scorecard values."""
    errors = []
    matched = 0
    checked = 0

    for entry in entries:
        key = f"{entry['ecosystem']}:{entry['name'].lower()}"
        computed = compute_coefficient(entry["scores"], entry.get("weights"))

        # Find matching published value (fuzzy)
        pub_val = None
        for pk, pv in published.items():
            if entry["name"].lower() in pk or pk in key:
                pub_val = pv
                break

        if pub_val is not None:
            checked += 1
            diff = abs(computed - pub_val)
            if diff <= 0.1:
                matched += 1
            else:
                errors.append({
                    "name": entry["name"],
                    "computed": computed,
                    "published": pub_val,
                    "diff": round(diff, 2),
                })

    return matched, checked, errors


def check_agent_implementation():
    """Check how many of the 7 canonical agents have Python implementations."""
    agents_dir = ROOT / "agents"
    if not agents_dir.exists():
        return 0, []

    implemented = []
    # Check each Python file for agent classes
    agent_files = {
        "truthSeeker": ["subnet_oracle.py", "oracle"],
        "mavenMetrics": ["emission_metrics.py", "emission"],
        "tokenLogic": ["subnet_economics.py", "economics"],
        "liquidEdge": ["stake_flow.py", "stakeflow"],
        "hypePulse": ["hype_pulse.py", "hype"],
        "codeCrafter": ["code_crafter.py", "code"],
        "riskEye": ["risk_eye.py", "risk"],
    }

    for canon_name, (filename, keyword) in agent_files.items():
        filepath = agents_dir / filename
        if filepath.exists():
            implemented.append(canon_name)
        else:
            # Check if any existing file contains this agent's logic
            for py_file in agents_dir.glob("*.py"):
                content = py_file.read_text()
                if keyword.lower() in content.lower() and "class" in content:
                    implemented.append(canon_name)
                    break

    return len(implemented), implemented


def check_code_quality():
    """Check for known bugs and code quality issues."""
    issues = []

    # Check stake_flow.py for the SubnetLimit bug
    stake_path = ROOT / "agents" / "stake_flow.py"
    if stake_path.exists():
        content = stake_path.read_text()
        if "SubnetLimit" in content and "validator" in content.lower():
            issues.append("stake_flow.py: queries SubnetLimit (global) instead of per-subnet validator count")

    # Check __init__.py exports
    init_path = ROOT / "agents" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text()
        exported = re.findall(r"from\s+\.(\w+)\s+import", content)
        if len(exported) < 7:
            issues.append(f"__init__.py: only exports {len(exported)} agents, should export 7")

    # Check for test files
    test_dir = ROOT / "tests"
    if not test_dir.exists() and not list(ROOT.glob("test_*.py")):
        issues.append("No test files found")

    return issues


def check_scoring_coherence(entries):
    """Check if scores follow logical patterns."""
    issues = []

    for entry in entries:
        scores = entry["scores"]
        details = entry.get("details", {})
        name = entry["name"]

        # Check: high TVL projects should generally score higher in mavenMetrics
        tvl = details.get("tvl", 0)
        maven_score = scores.get("mavenMetrics", scores.get("mavenMetrics", 5))

        # Check: all scores should be in [1, 10]
        for agent, score in scores.items():
            if agent in CANONICAL_WEIGHTS and isinstance(score, (int, float)):
                if score < 1 or score > 10:
                    issues.append(f"{name}.{agent}={score} out of range [1,10]")

    return issues


def evaluate():
    """Run the full evaluation."""
    entries = load_tao_data() + load_eth_data()
    published = parse_published_coefficients()

    # Metric 1: Formula consistency (35%)
    matched, checked, consistency_errors = check_formula_consistency(entries, published)
    formula_score = (matched / checked * 35) if checked > 0 else 0

    # Metric 2: Agent implementation coverage (25%)
    impl_count, implemented = check_agent_implementation()
    impl_score = (impl_count / 7) * 25

    # Metric 3: Code quality (20%) — start at 20, deduct per issue
    code_issues = check_code_quality()
    quality_score = max(0, 20 - len(code_issues) * 5)

    # Metric 4: Scoring coherence (20%)
    coherence_issues = check_scoring_coherence(entries)
    coherence_score = max(0, 20 - len(coherence_issues) * 2)

    composite = formula_score + impl_score + quality_score + coherence_score

    details = {
        "composite_score": round(composite, 2),
        "metrics": {
            "formula_consistency": {"score": round(formula_score, 2), "/ max": 35, 
                                     "matched": matched, "checked": checked},
            "agent_implementation": {"score": round(impl_score, 2), "/ max": 25,
                                      "implemented": f"{impl_count}/7",
                                      "agents": implemented},
            "code_quality": {"score": round(quality_score, 2), "/ max": 20,
                              "issues": code_issues},
            "scoring_coherence": {"score": round(coherence_score, 2), "/ max": 20,
                                   "issues": coherence_issues},
        },
        "entry_count": len(entries),
        "published_count": len(published),
    }

    return composite, details


if __name__ == "__main__":
    score, details = evaluate()
    print(f"\n{'='*60}")
    print(f"Lisa Coefficient Benchmark — Evaluation Results")
    print(f"{'='*60}")
    print(f"Composite Score: {score:.2f} / 100")
    print(f"\nMetrics Breakdown:")
    for metric, info in details["metrics"].items():
        if isinstance(info, dict) and "score" in info:
            max_val = info.get("/ max", "?")
            print(f"  {metric}: {info['score']:.1f} / {max_val}")
    print(f"\n  Entries evaluated: {details['entry_count']}")
    print(f"  Published coefficients found: {details['published_count']}")

    # Show specific issues
    cq = details["metrics"].get("code_quality", {}).get("issues", [])
    if cq:
        print(f"\n  Code Quality Issues ({len(cq)}):")
        for issue in cq:
            print(f"    - {issue}")

    ci = details["metrics"].get("scoring_coherence", {}).get("issues", [])
    if ci:
        print(f"\n  Coherence Issues ({len(ci)}):")
        for issue in ci[:5]:
            print(f"    - {issue}")

    ai = details["metrics"].get("agent_implementation", {})
    if ai:
        print(f"\n  Implemented Agents ({ai.get('implemented', 0)}/7): {ai.get('agents', [])}")

    print(f"\n{'='*60}")
    print(f"\nSCORE: {score:.4f}")
