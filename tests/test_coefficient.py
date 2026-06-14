#!/usr/bin/env python3
"""
Tests for the Lisa Coefficient scoring framework.

Covers three areas:
  1. compute_coefficient correctness for known score/weight sets
  2. All 7 canonical agents can be imported from the agents package
  3. Each agent keeps its score within the [1, 10] range

Runs under both `python -m pytest tests/ -v` and
`python -m unittest tests.test_coefficient` (and `python tests/test_coefficient.py`).
"""

import os
import sys

import unittest

# Make the repo root importable so `import agents` and `from eval import ...` work.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from eval import compute_coefficient, CANONICAL_WEIGHTS  # noqa: E402
import agents  # noqa: E402
from agents import (  # noqa: E402
    EmissionMetricsAgent,
    SubnetOracleAgent,
    SubnetEconomicsAgent,
    StakeFlowAgent,
    HypePulseAgent,
    CodeCrafterAgent,
    RiskEyeAgent,
)

ALL_AGENTS = [
    EmissionMetricsAgent,
    SubnetOracleAgent,
    SubnetEconomicsAgent,
    StakeFlowAgent,
    HypePulseAgent,
    CodeCrafterAgent,
    RiskEyeAgent,
]


# --------------------------------------------------------------------------- #
# compute_coefficient
# --------------------------------------------------------------------------- #
def test_coefficient_empty_scores_defaults_to_five():
    # No scores → every agent defaults to 5.0 → weighted avg = 5.0
    assert compute_coefficient({}) == 5.0


def test_coefficient_all_perfect_scores():
    scores = {name: 10.0 for name in CANONICAL_WEIGHTS}
    assert compute_coefficient(scores) == 10.0


def test_coefficient_all_minimum_scores():
    scores = {name: 1.0 for name in CANONICAL_WEIGHTS}
    assert compute_coefficient(scores) == 1.0


def test_coefficient_single_override():
    # truthSeeker (weight 0.20) at 10, everything else default 5
    expected = 10 * 0.20 + 5 * 0.80
    assert compute_coefficient({"truthSeeker": 10.0}) == round(expected, 2)


def test_coefficient_missing_agent_uses_default():
    # Provide 6 of 7; the missing one (riskEye, weight 0.10) defaults to 5
    scores = {name: 10.0 for name in CANONICAL_WEIGHTS if name != "riskEye"}
    expected = 10 * 0.90 + 5 * 0.10
    assert compute_coefficient(scores) == round(expected, 2)


def test_coefficient_custom_weights():
    custom = {"truthSeeker": 1.0}
    # With a single weight of 1.0, the coefficient equals that score directly
    assert compute_coefficient({"truthSeeker": 7.3}, custom) == 7.3


def test_coefficient_non_numeric_falls_back_to_default():
    # A non-numeric value should be treated as the 5.0 default
    scores = {name: 10.0 for name in CANONICAL_WEIGHTS}
    scores["riskEye"] = "n/a"
    expected = 10 * 0.90 + 5 * 0.10
    assert compute_coefficient(scores) == round(expected, 2)


def test_coefficient_rounded_to_two_decimals():
    result = compute_coefficient({"truthSeeker": 7.3, "mavenMetrics": 6.1})
    # 2 decimal places
    assert round(result, 2) == result


# --------------------------------------------------------------------------- #
# Agent imports
# --------------------------------------------------------------------------- #
def test_all_seven_agents_importable():
    expected = {
        "EmissionMetricsAgent",
        "SubnetOracleAgent",
        "SubnetEconomicsAgent",
        "StakeFlowAgent",
        "HypePulseAgent",
        "CodeCrafterAgent",
        "RiskEyeAgent",
    }
    assert set(agents.__all__) == expected
    for cls in ALL_AGENTS:
        assert isinstance(cls, type)


def test_agents_init_exports_seven():
    import re
    init_path = os.path.join(ROOT, "agents", "__init__.py")
    with open(init_path) as f:
        content = f.read()
    exported = re.findall(r"from\s+\.(\w+)\s+import", content)
    assert len(exported) >= 7


# --------------------------------------------------------------------------- #
# Score range [1, 10]
# --------------------------------------------------------------------------- #
def _check_range(agent, args):
    result = agent.score(*args)
    assert 1.0 <= result.total <= 10.0, f"{type(agent).__name__} total out of range: {result.total}"
    return result.total


def test_stake_flow_score_in_range():
    _check_range(StakeFlowAgent(), (1,))
    _check_range(StakeFlowAgent(), (999,))


def test_subnet_economics_score_in_range():
    _check_range(SubnetEconomicsAgent(), (1,))


def test_hype_pulse_score_in_range():
    _check_range(HypePulseAgent(), (80,))
    _check_range(HypePulseAgent(), (999,))


def test_code_crafter_score_in_range():
    _check_range(CodeCrafterAgent(), (80,))
    _check_range(CodeCrafterAgent(), (999,))


def test_risk_eye_score_in_range():
    _check_range(RiskEyeAgent(), (80,))
    _check_range(RiskEyeAgent(), (999,))


# --------------------------------------------------------------------------- #
# unittest entry point (so the file also works with python -m unittest / direct run)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    unittest.main()
