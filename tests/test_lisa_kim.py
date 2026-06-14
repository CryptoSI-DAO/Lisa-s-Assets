#!/usr/bin/env python3
"""
Tests for Lisa Kim — the Meta-Agent.

Covers three areas:
  1. First-time project scoring (weighted average correctness)
  2. Trajectory computation with mock historical data
  3. Momentum classification (improving / declining / stable)

Runs under ``python -m pytest tests/ -v``,
``python -m unittest tests.test_lisa_kim``,
and ``python tests/test_lisa_kim.py``.
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta

# Make repo root importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents.lisa_kim import LisaKimAgent, LisaKimScore  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _uniform_scores(value: float) -> dict:
    """All 7 agents at the same score."""
    return {
        'truth_seeker': value,
        'maven_metrics': value,
        'token_logic': value,
        'liquid_edge': value,
        'hype_pulse': value,
        'code_crafter': value,
        'risk_eye': value,
    }


def _days_ago_iso(days: int) -> str:
    """ISO date string for N days ago."""
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


# ════════════════════════════════════════════════════════════════════════════
#  1. FIRST-TIME PROJECT SCORING
# ════════════════════════════════════════════════════════════════════════════

def test_first_time_uniform_scores():
    """All agents at same value → coefficient equals that value."""
    agent = LisaKimAgent()
    for val in [1.0, 5.0, 7.5, 10.0]:
        result = _run(agent.analyze(_uniform_scores(val)))
        assert result.total == val, f"Expected {val}, got {result.total}"
        assert result.trajectory is None


def test_first_time_weighted_average():
    """Verify exact weighted average computation."""
    agent = LisaKimAgent()
    scores = {
        'truth_seeker': 8.0,
        'maven_metrics': 6.0,
        'token_logic': 7.0,
        'liquid_edge': 5.0,
        'hype_pulse': 9.0,
        'code_crafter': 4.0,
        'risk_eye': 6.0,
    }
    result = _run(agent.analyze(scores))
    expected = (
        8.0 * 0.20 + 6.0 * 0.20 + 7.0 * 0.15 + 5.0 * 0.15 +
        9.0 * 0.10 + 4.0 * 0.10 + 6.0 * 0.10
    )
    assert abs(result.total - round(expected, 2)) < 0.01, \
        f"Expected {expected:.2f}, got {result.total}"


def test_first_time_missing_agents_default():
    """Missing agent scores default to 5.0."""
    agent = LisaKimAgent()
    result = _run(agent.analyze({'truth_seeker': 10.0}))
    expected = 10.0 * 0.20 + 5.0 * 0.80
    assert abs(result.total - round(expected, 2)) < 0.01


def test_first_time_no_trajectory():
    """First-time projects have trajectory=None."""
    agent = LisaKimAgent()
    result = _run(agent.analyze(_uniform_scores(7.0)))
    assert result.trajectory is None


def test_camelcase_keys_accepted():
    """camelCase keys (from eval.py CANONICAL_WEIGHTS) are normalized."""
    agent = LisaKimAgent()
    scores = {
        'truthSeeker': 10.0,
        'mavenMetrics': 10.0,
        'tokenLogic': 10.0,
        'liquidEdge': 10.0,
        'hypePulse': 10.0,
        'codeCrafter': 10.0,
        'riskEye': 10.0,
    }
    result = _run(agent.analyze(scores))
    assert result.total == 10.0


def test_short_alias_keys_accepted():
    """Short alias keys (oracle, emission, economics, etc.) are mapped."""
    agent = LisaKimAgent()
    scores = {
        'oracle': 8.0, 'emission': 8.0, 'economics': 8.0,
        'stakeflow': 8.0, 'hype': 8.0, 'code': 8.0, 'risk': 8.0,
    }
    result = _run(agent.analyze(scores))
    assert result.total == 8.0


def test_coefficient_range():
    """Coefficient always clamped to [0, 10]."""
    agent = LisaKimAgent()
    for val in [0.0, 1.0, 10.0]:
        result = _run(agent.analyze(_uniform_scores(val)))
        assert 0.0 <= result.total <= 10.0


def test_verdict_is_nonempty_string():
    """Verdict is a non-empty string of reasonable length."""
    agent = LisaKimAgent()
    result = _run(agent.analyze(_uniform_scores(6.0)))
    assert isinstance(result.verdict, str)
    assert len(result.verdict) > 10


def test_agent_weights_populated():
    """agent_weights contains all 7 agents, weights sum to 1.0."""
    agent = LisaKimAgent()
    result = _run(agent.analyze(_uniform_scores(5.0)))
    assert len(result.agent_weights) == 7
    assert abs(sum(result.agent_weights.values()) - 1.0) < 0.001


def test_details_breakdown():
    """Details dict contains per-agent weighted_scores breakdown."""
    agent = LisaKimAgent()
    result = _run(agent.analyze({'truth_seeker': 8.0}))
    assert 'weighted_scores' in result.details
    assert 'raw_coefficient' in result.details
    assert 'truth_seeker' in result.details['weighted_scores']
    assert result.details['weighted_scores']['truth_seeker']['score'] == 8.0


def test_non_numeric_score_falls_back():
    """Non-numeric agent scores default to 5.0."""
    agent = LisaKimAgent()
    scores = _uniform_scores(10.0)
    scores['risk_eye'] = "N/A"
    result = _run(agent.analyze(scores))
    expected = 10.0 * 0.90 + 5.0 * 0.10
    assert abs(result.total - round(expected, 2)) < 0.01


# ════════════════════════════════════════════════════════════════════════════
#  2. TRAJECTORY COMPUTATION
# ════════════════════════════════════════════════════════════════════════════

def test_trajectory_basic():
    """Trajectory is computed when previous_reports provided."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 5.5, 'date': _days_ago_iso(90), 'coefficient': 5.5},
    ]
    result = _run(agent.analyze(_uniform_scores(7.0), previous_reports))
    assert result.trajectory is not None
    assert result.trajectory['previous_score'] == 5.5
    assert result.trajectory['current_score'] == 7.0


def test_trajectory_improvement_value():
    """improvement = current_coefficient - previous_coefficient."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 5.0, 'date': _days_ago_iso(30), 'coefficient': 5.0},
    ]
    result = _run(agent.analyze(_uniform_scores(7.0), previous_reports))
    assert result.trajectory['improvement'] == 2.0


def test_trajectory_projected_score():
    """Projected score extrapolates improvement_rate × 3 months."""
    agent = LisaKimAgent()
    # ~3 months ago coefficient was 5.0, now 7.0
    # improvement = 2.0, months ≈ 3, rate ≈ 0.667
    # projected = 7.0 + 0.667 * 3 ≈ 9.0
    previous_reports = [
        {'score': 5.0, 'date': _days_ago_iso(91), 'coefficient': 5.0},
    ]
    result = _run(agent.analyze(_uniform_scores(7.0), previous_reports))
    proj = result.trajectory['projected_score']
    assert 8.5 <= proj <= 9.5, f"Projected {proj} outside expected range [8.5, 9.5]"


def test_trajectory_projection_date():
    """Projection date is ~90 days (3 months) from now."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 5.0, 'date': _days_ago_iso(30), 'coefficient': 5.0},
    ]
    result = _run(agent.analyze(_uniform_scores(6.0), previous_reports))
    proj_date = result.trajectory['projection_date']
    expected = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    assert proj_date == expected


def test_trajectory_most_recent_used():
    """Most recent report (by date) is used for previous_score."""
    agent = LisaKimAgent()
    reports = [
        {'score': 3.0, 'date': '2025-01-15', 'coefficient': 3.0},
        {'score': 5.5, 'date': '2025-07-15', 'coefficient': 5.5},
        {'score': 4.5, 'date': '2025-04-15', 'coefficient': 4.5},
    ]
    result = _run(agent.analyze(_uniform_scores(7.0), reports))
    assert result.trajectory['previous_score'] == 5.5
    assert result.trajectory['report_count'] == 3


def test_trajectory_report_count():
    """Trajectory includes total number of historical reports."""
    agent = LisaKimAgent()
    reports = [
        {'score': 3.0, 'date': '2025-01-15', 'coefficient': 3.0},
        {'score': 4.0, 'date': '2025-04-15', 'coefficient': 4.0},
    ]
    result = _run(agent.analyze(_uniform_scores(6.0), reports))
    assert result.trajectory['report_count'] == 2


# ════════════════════════════════════════════════════════════════════════════
#  3. MOMENTUM CLASSIFICATION
# ════════════════════════════════════════════════════════════════════════════

def test_momentum_improving():
    """improvement > 0.2 → 'improving'."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 5.0, 'date': _days_ago_iso(30), 'coefficient': 5.0},
    ]
    result = _run(agent.analyze(_uniform_scores(8.0), previous_reports))
    assert result.trajectory['momentum'] == 'improving'


def test_momentum_declining():
    """improvement < -0.2 → 'declining'."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 8.0, 'date': _days_ago_iso(30), 'coefficient': 8.0},
    ]
    result = _run(agent.analyze(_uniform_scores(5.0), previous_reports))
    assert result.trajectory['momentum'] == 'declining'


def test_momentum_stable():
    """|improvement| ≤ 0.2 → 'stable'."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 6.0, 'date': _days_ago_iso(30), 'coefficient': 6.0},
    ]
    result = _run(agent.analyze(_uniform_scores(6.1), previous_reports))
    assert result.trajectory['momentum'] == 'stable'


def test_momentum_bonus_improving():
    """Improving projects get +0.3 momentum bonus."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 4.0, 'date': _days_ago_iso(30), 'coefficient': 4.0},
    ]
    # raw = 7.0, previous = 4.0 → improving → +0.3
    result = _run(agent.analyze(_uniform_scores(7.0), previous_reports))
    assert result.total == round(7.0 + 0.3, 2)


def test_momentum_penalty_declining():
    """Declining projects get -0.3 momentum penalty."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 8.0, 'date': _days_ago_iso(30), 'coefficient': 8.0},
    ]
    # raw = 5.0, previous = 8.0 → declining → -0.3
    result = _run(agent.analyze(_uniform_scores(5.0), previous_reports))
    assert result.total == round(5.0 - 0.3, 2)


def test_momentum_no_adjustment_stable():
    """Stable projects get no momentum adjustment."""
    agent = LisaKimAgent()
    previous_reports = [
        {'score': 6.0, 'date': _days_ago_iso(30), 'coefficient': 6.0},
    ]
    # raw = 6.1, previous = 6.0 → improvement 0.1 → stable → 0.0
    result = _run(agent.analyze(_uniform_scores(6.1), previous_reports))
    assert result.total == round(6.1, 2)


# ════════════════════════════════════════════════════════════════════════════
#  SYNC WRAPPER & INTEGRATION
# ════════════════════════════════════════════════════════════════════════════

def test_sync_score_wrapper():
    """score() sync wrapper produces same result as analyze()."""
    agent = LisaKimAgent()
    result = agent.score(_uniform_scores(7.5))
    assert isinstance(result, LisaKimScore)
    assert result.total == 7.5


def test_lisa_kim_importable_from_agents():
    """LisaKimAgent is exported from the agents package."""
    import agents
    assert hasattr(agents, 'LisaKimAgent')
    assert 'LisaKimAgent' in agents.__all__


# ════════════════════════════════════════════════════════════════════════════
#  DIRECT-RUN ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    _funcs = [v for k, v in sorted(globals().items())
              if k.startswith("test_") and callable(v)]
    failures = 0
    for fn in _funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(_funcs) - failures}/{len(_funcs)} tests passed")
    sys.exit(1 if failures else 0)
