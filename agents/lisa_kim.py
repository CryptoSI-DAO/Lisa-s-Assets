#!/usr/bin/env python3
"""
Lisa Kim Agent 🟡
Part of the Lisa's Assets Subnet Scoring Framework.

The META-AGENT. Lisa Kim does NOT fetch her own data. She deploys 7 specialist
agents, reads their findings, and synthesizes everything into the Lisa
Coefficient — a single 0-10 score that captures a project's quality.

Her unique edge: temporal analysis. For projects with prior reports she
computes trajectory, momentum, and forward projections — she sees where
a project is *going*, not just where it is.

Weight model (matches CANONICAL_WEIGHTS in eval.py):
    TruthSeeker   20%   MavenMetrics   20%   TokenLogic   15%
    LiquidEdge    15%   HypePulse      10%   CodeCrafter  10%
    RiskEye       10%
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

# Lisa Kim orchestrates all 7 specialist agents
from .subnet_oracle import SubnetOracleAgent
from .emission_metrics import EmissionMetricsAgent
from .subnet_economics import SubnetEconomicsAgent
from .stake_flow import StakeFlowAgent
from .hype_pulse import HypePulseAgent
from .code_crafter import CodeCrafterAgent
from .risk_eye import RiskEyeAgent


@dataclass
class LisaKimScore:
    """Final output from Lisa Kim's meta-analysis."""
    total: float            # 0-10 — the final Lisa Coefficient
    verdict: str            # 2-3 sentence summary
    notes: list             # supporting observations
    trajectory: Optional[dict]  # None for first-time; dict for repeat projects
    agent_weights: dict     # which agents contributed and their weights
    details: dict           # full breakdown of coefficient computation


class LisaKimAgent:
    """Lisa Kim — the meta-agent that synthesizes 7 specialist scores.

    She does NOT fetch her own data. She reads the 7 agents' findings and
    computes the Lisa Coefficient: a weighted average enhanced by temporal
    trajectory analysis for projects with historical reports.

    Usage
    -----
    ::

        agent = LisaKimAgent()

        # First-time project (snapshot only)
        score = await agent.analyze({"truth_seeker": 8.0, ...})

        # Repeat project (adds trajectory + projection)
        score = await agent.analyze(
            {"truth_seeker": 8.0, ...},
            previous_reports=[
                {"score": 5.5, "date": "2025-03-01", "coefficient": 5.5},
            ],
        )
    """

    # ── Weight configuration (sums to 1.0) ──────────────────────────────────
    WEIGHTS = {
        'truth_seeker': 0.20,
        'maven_metrics': 0.20,
        'token_logic': 0.15,
        'liquid_edge': 0.15,
        'hype_pulse': 0.10,
        'code_crafter': 0.10,
        'risk_eye': 0.10,
    }

    # Human-readable display names for each specialist agent
    AGENT_LABELS = {
        'truth_seeker': 'TruthSeeker',
        'maven_metrics': 'MavenMetrics',
        'token_logic': 'TokenLogic',
        'liquid_edge': 'LiquidEdge',
        'hype_pulse': 'HypePulse',
        'code_crafter': 'CodeCrafter',
        'risk_eye': 'RiskEye',
    }

    # Mapping from various incoming key formats → canonical WEIGHTS keys.
    # Accepts snake_case, camelCase (eval.py), and short aliases (TAO_KEY_MAP).
    _KEY_ALIASES = {
        # snake_case (canonical)
        'truth_seeker': 'truth_seeker',
        'maven_metrics': 'maven_metrics',
        'token_logic': 'token_logic',
        'liquid_edge': 'liquid_edge',
        'hype_pulse': 'hype_pulse',
        'code_crafter': 'code_crafter',
        'risk_eye': 'risk_eye',
        # camelCase (used in eval.py / CANONICAL_WEIGHTS)
        'truthSeeker': 'truth_seeker',
        'mavenMetrics': 'maven_metrics',
        'tokenLogic': 'token_logic',
        'liquidEdge': 'liquid_edge',
        'hypePulse': 'hype_pulse',
        'codeCrafter': 'code_crafter',
        'riskEye': 'risk_eye',
        # short aliases (used in TAO_KEY_MAP in eval.py)
        'oracle': 'truth_seeker',
        'emission': 'maven_metrics',
        'economics': 'token_logic',
        'stakeflow': 'liquid_edge',
        'stake_flow': 'liquid_edge',
        'hype': 'hype_pulse',
        'code': 'code_crafter',
        'risk': 'risk_eye',
        # class/file-name-based
        'subnetoracle': 'truth_seeker',
        'subnet_oracle': 'truth_seeker',
        'emissionmetrics': 'maven_metrics',
        'emission_metrics': 'maven_metrics',
        'subneteconomics': 'token_logic',
        'subnet_economics': 'token_logic',
    }

    # Momentum thresholds and bonus
    MOMENTUM_THRESHOLD = 0.2     # |improvement| above this = directional
    MOMENTUM_BONUS = 0.3         # ±0.3 applied based on trajectory
    DEFAULT_SCORE = 5.0          # fallback when an agent score is missing/invalid

    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════════════

    async def analyze(
        self,
        agent_scores: dict,
        previous_reports: Optional[list] = None,
    ) -> LisaKimScore:
        """Synthesize 7 specialist scores into the Lisa Coefficient.

        Parameters
        ----------
        agent_scores : dict
            Mapping of agent identifier → score (1-10). Accepts snake_case,
            camelCase, or short-alias keys. Missing agents default to 5.0.
        previous_reports : list[dict] | None
            Historical reports, each containing ``{score, date, coefficient}``.
            When provided with ≥1 entry, temporal trajectory is computed and
            a momentum bonus/penalty (±0.3) is applied.

        Returns
        -------
        LisaKimScore
        """
        # ── Normalize incoming keys & compute weighted average ──────────────
        normalized = self._normalize_scores(agent_scores)
        raw_coefficient = self._weighted_average(normalized)

        notes: list = []
        details: dict = {
            'weighted_scores': {},
            'raw_coefficient': round(raw_coefficient, 2),
        }

        # Record per-agent contributions
        for key, weight in self.WEIGHTS.items():
            score = normalized.get(key, self.DEFAULT_SCORE)
            details['weighted_scores'][key] = {
                'label': self.AGENT_LABELS[key],
                'score': score,
                'weight': weight,
                'contribution': round(score * weight, 3),
            }

        # ── Temporal trajectory (if history available) ─────────────────────
        trajectory = None
        momentum_adjustment = 0.0

        if previous_reports:
            trajectory = self._compute_trajectory(
                raw_coefficient, previous_reports
            )
            if trajectory:
                momentum = trajectory['momentum']
                if momentum == 'improving':
                    momentum_adjustment = self.MOMENTUM_BONUS
                    notes.append(
                        f"📈 Trajectory improving "
                        f"(+{self.MOMENTUM_BONUS} momentum bonus) — "
                        f"projected {trajectory['projected_score']:.1f} "
                        f"by {trajectory['projection_date']}"
                    )
                elif momentum == 'declining':
                    momentum_adjustment = -self.MOMENTUM_BONUS
                    notes.append(
                        f"📉 Trajectory declining "
                        f"(-{self.MOMENTUM_BONUS} momentum penalty) — "
                        f"projected {trajectory['projected_score']:.1f} "
                        f"by {trajectory['projection_date']}"
                    )
                else:
                    notes.append(
                        f"➡️ Trajectory stable — "
                        f"projected {trajectory['projected_score']:.1f} "
                        f"in 3 months"
                    )
                details['momentum_adjustment'] = momentum_adjustment

        # Apply momentum adjustment and clamp to [0, 10]
        final_coefficient = max(
            0.0, min(10.0, raw_coefficient + momentum_adjustment)
        )
        final_coefficient = round(final_coefficient, 2)

        details['final_coefficient'] = final_coefficient
        details['has_trajectory'] = trajectory is not None

        # ── Strength / weakness highlights ─────────────────────────────────
        strengths, weaknesses = self._identify_extremes(normalized)
        for label, score in strengths:
            notes.append(f"💪 {label} scoring high ({score:.1f})")
        for label, score in weaknesses:
            notes.append(f"⚠️ {label} scoring low ({score:.1f})")

        # ── Verdict ────────────────────────────────────────────────────────
        verdict = self._generate_verdict(
            final_coefficient, normalized, trajectory
        )

        return LisaKimScore(
            total=final_coefficient,
            verdict=verdict,
            notes=notes,
            trajectory=trajectory,
            agent_weights=dict(self.WEIGHTS),
            details=details,
        )

    def score(
        self, agent_scores: dict, previous_reports: Optional[list] = None
    ) -> LisaKimScore:
        """Synchronous wrapper for :meth:`analyze`."""
        return asyncio.run(self.analyze(agent_scores, previous_reports))

    # ══════════════════════════════════════════════════════════════════════
    #  INTERNAL COMPUTATION
    # ══════════════════════════════════════════════════════════════════════

    def _normalize_scores(self, agent_scores: dict) -> dict:
        """Map various incoming key formats to canonical WEIGHTS keys.

        Ensures all 7 canonical keys are present (defaults to ``DEFAULT_SCORE``
        for any missing/non-numeric agent).
        """
        normalized = {}
        for key, value in agent_scores.items():
            canonical = self._KEY_ALIASES.get(str(key).strip())
            if canonical:
                normalized[canonical] = value
            else:
                # Pass through — might already be canonical snake_case
                normalized[key] = value

        # Ensure all canonical keys exist and are numeric floats
        for k in self.WEIGHTS:
            v = normalized.get(k, self.DEFAULT_SCORE)
            normalized[k] = float(v) if isinstance(v, (int, float)) else self.DEFAULT_SCORE

        return normalized

    def _weighted_average(self, normalized: dict) -> float:
        """Compute the weighted average of the 7 agent scores."""
        total = 0.0
        for key, weight in self.WEIGHTS.items():
            total += normalized.get(key, self.DEFAULT_SCORE) * weight
        return total

    def _compute_trajectory(
        self, current_coefficient: float, previous_reports: list
    ) -> Optional[dict]:
        """Compute temporal trajectory from historical reports.

        Each report should contain ``{score, date, coefficient}``.
        Uses the most recent report as the baseline.
        """
        if not previous_reports:
            return None

        # Find the most recent historical report by date
        sorted_reports = self._sort_by_date(previous_reports)
        most_recent = sorted_reports[-1]

        previous_coefficient = most_recent.get('coefficient')
        if previous_coefficient is None:
            previous_coefficient = most_recent.get('score')
        if previous_coefficient is None:
            return None

        previous_coefficient = float(previous_coefficient)
        previous_date = self._parse_date(most_recent.get('date'))
        now = datetime.now()

        # Months elapsed between most-recent report and now
        if previous_date:
            months_elapsed = self._months_between(previous_date, now)
            months_elapsed = max(months_elapsed, 0.01)  # guard div-by-zero
        else:
            months_elapsed = 1.0

        improvement = round(current_coefficient - previous_coefficient, 2)

        # Momentum classification
        if improvement > self.MOMENTUM_THRESHOLD:
            momentum = 'improving'
        elif improvement < -self.MOMENTUM_THRESHOLD:
            momentum = 'declining'
        else:
            momentum = 'stable'

        improvement_rate = round(improvement / months_elapsed, 3)

        # Forward projection: current + (rate × 3 months), clamped [0, 10]
        projected_score = current_coefficient + (improvement_rate * 3)
        projected_score = round(max(0.0, min(10.0, projected_score)), 2)

        projection_date = (now + timedelta(days=90)).strftime('%Y-%m-%d')

        return {
            'previous_score': round(previous_coefficient, 2),
            'current_score': round(current_coefficient, 2),
            'improvement': improvement,
            'momentum': momentum,
            'months_elapsed': round(months_elapsed, 2),
            'improvement_rate': improvement_rate,
            'projected_score': projected_score,
            'projection_date': projection_date,
            'previous_date': (
                previous_date.strftime('%Y-%m-%d') if previous_date else None
            ),
            'report_count': len(previous_reports),
        }

    # ══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _parse_date(date_val) -> Optional[datetime]:
        """Parse a date value (string or datetime) into a datetime."""
        if date_val is None:
            return None
        if isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, str):
            for fmt in (
                '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f',
                '%Y/%m/%d', '%B %Y', '%b %Y',
            ):
                try:
                    return datetime.strptime(date_val.strip(), fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(date_val)
            except (ValueError, TypeError):
                return None
        return None

    @staticmethod
    def _months_between(start: datetime, end: datetime) -> float:
        """Approximate fractional months between two dates."""
        return (end - start).days / 30.44  # average month length

    def _sort_by_date(self, reports: list) -> list:
        """Sort reports chronologically by their ``date`` field."""
        def sort_key(r):
            return self._parse_date(r.get('date')) or datetime.min
        return sorted(reports, key=sort_key)

    def _identify_extremes(self, normalized: dict) -> tuple:
        """Identify top strengths (≥7.0) and weaknesses (<4.0).

        Returns ``(strengths, weaknesses)`` — lists of ``(label, score)`` tuples.
        """
        scored = [
            (self.AGENT_LABELS[key], normalized.get(key, self.DEFAULT_SCORE))
            for key in self.WEIGHTS
        ]
        strengths = sorted(
            [(l, s) for l, s in scored if s >= 7.0],
            key=lambda x: -x[1],
        )
        weaknesses = sorted(
            [(l, s) for l, s in scored if s < 4.0],
            key=lambda x: x[1],
        )
        return strengths, weaknesses

    def _generate_verdict(
        self,
        coefficient: float,
        normalized: dict,
        trajectory: Optional[dict],
    ) -> str:
        """Generate a 2-3 sentence verdict summarizing the project."""
        if coefficient >= 8.0:
            tier = "exceptional"
        elif coefficient >= 6.5:
            tier = "strong"
        elif coefficient >= 5.0:
            tier = "moderate"
        elif coefficient >= 3.5:
            tier = "weak"
        else:
            tier = "high-risk"

        strengths, weaknesses = self._identify_extremes(normalized)
        parts: list = []

        # Sentence 1 — overall assessment
        parts.append(f"Lisa Coefficient {coefficient:.1f}/10 — {tier} profile.")

        # Sentence 2 — strengths & weaknesses
        if strengths and weaknesses:
            parts.append(
                f"Strengths in {strengths[0][0]} ({strengths[0][1]:.1f}); "
                f"concerns in {weaknesses[0][0]} ({weaknesses[0][1]:.1f})."
            )
        elif strengths:
            parts.append(
                f"Notable strengths across "
                f"{', '.join(l for l, _ in strengths[:2])}."
            )
        elif weaknesses:
            parts.append(
                f"Key concerns in "
                f"{', '.join(l for l, _ in weaknesses[:2])}."
            )
        else:
            parts.append("No agent flagged significant outliers.")

        # Sentence 3 — trajectory (if available)
        if trajectory:
            momentum = trajectory['momentum']
            proj = trajectory['projected_score']
            if momentum == 'improving':
                parts.append(
                    f"Trajectory improving — projected to reach {proj:.1f} "
                    f"within 3 months."
                )
            elif momentum == 'declining':
                parts.append(
                    f"Trajectory declining — projected to fall to {proj:.1f} "
                    f"within 3 months if current trends hold."
                )
            else:
                parts.append(
                    f"Trajectory stable, projected at {proj:.1f} for "
                    f"3 months out."
                )

        return ' '.join(parts)


# ════════════════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lisa Kim Meta-Agent 🟡")
    parser.add_argument(
        "--scores", type=str, required=True,
        help='JSON dict of agent scores, e.g. \'{"truth_seeker": 8.0, ...}\'',
    )
    parser.add_argument(
        "--history", type=str, default=None,
        help="JSON list of previous reports [{score, date, coefficient}, ...]",
    )
    args = parser.parse_args()

    agent = LisaKimAgent()
    result = agent.score(
        json.loads(args.scores),
        json.loads(args.history) if args.history else None,
    )

    print(json.dumps({
        "lisa_coefficient": result.total,
        "verdict": result.verdict,
        "notes": result.notes,
        "trajectory": result.trajectory,
        "agent_weights": result.agent_weights,
        "details": result.details,
    }, indent=2, default=str))
