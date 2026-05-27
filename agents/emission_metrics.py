#!/usr/bin/env python3
"""
EmissionMetrics Agent 🧮
Part of the Lisa's Assets Subnet Scoring Framework.

Evaluates a Bittensor subnet's emission metrics on a 1-10 scale.
Connects to Finney RPC and queries on-chain emission data.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional
from async_substrate_interface import AsyncSubstrateInterface

FINNEY_WSS = "wss://entrypoint-finney.opentensor.ai:443"


@dataclass
class EmissionScore:
    total: float  # 1-10
    rank_score: float
    inflow_score: float
    trend_score: float
    details: dict
    notes: list[str]


class EmissionMetricsAgent:
    """
    Analyzes subnet emission data:
    - Daily emission amount (TAO/day)
    - TAO inflow (direct TAO from root network)
    - Alpha inflow (subnet alpha token flow)
    - Pruning rank (competitive position)
    - Emission trend (vs previous month)
    """

    def score(self, netuid: int, taostats_rank: Optional[int] = None,
              previous_data: Optional[dict] = None) -> EmissionScore:
        """Synchronous wrapper for the async scoring method."""
        return asyncio.run(self._score_async(netuid, taostats_rank, previous_data))

    async def _score_async(self, netuid: int, taostats_rank: Optional[int] = None,
                           previous_data: Optional[dict] = None) -> EmissionScore:
        async with AsyncSubstrateInterface(FINNEY_WSS) as substrate:
            # Query on-chain emission data
            tao_in = await self._safe_query(substrate, "SubnetTaoInEmission", [netuid])
            alpha_in = await self._safe_query(substrate, "SubnetAlphaInEmission", [netuid])
            alpha_out = await self._safe_query(substrate, "SubnetAlphaOutEmission", [netuid])
            block_em = await self._safe_query(substrate, "BlockEmission", [])
            tao_weight = await self._safe_query(substrate, "TaoWeight", [])
            root_prop = await self._safe_query(substrate, "RootProp", [netuid])
            subnet_volume = await self._safe_query(substrate, "SubnetVolume", [netuid])
            moving_price = await self._safe_query(substrate, "SubnetMovingPrice", [netuid])

            notes = []
            details = {
                "netuid": netuid,
                "tao_in_emission_raw": tao_in,
                "alpha_in_emission_raw": alpha_in,
                "alpha_out_emission_raw": alpha_out,
                "block_emission_raw": block_em,
            }

            # --- Rank Score (1-5) ---
            # Based on pruning rank from taostats (1 = best)
            if taostats_rank is not None:
                if taostats_rank <= 3:
                    rank_score = 5.0
                    notes.append(f"Top-3 pruning rank (#{taostats_rank}) — highest emission priority")
                elif taostats_rank <= 10:
                    rank_score = 4.0
                    notes.append(f"Top-10 pruning rank (#{taostats_rank}) — strong emission priority")
                elif taostats_rank <= 25:
                    rank_score = 3.0
                    notes.append(f"Top-25 pruning rank (#{taostats_rank}) — moderate priority")
                elif taostats_rank <= 50:
                    rank_score = 2.0
                    notes.append(f"Mid-tier pruning rank (#{taostats_rank})")
                else:
                    rank_score = 1.0
                    notes.append(f"Low pruning rank (#{taostats_rank}) — emission vulnerable")
            else:
                rank_score = 2.5  # unknown
                notes.append("Pruning rank unknown — defaulting to mid-score")

            # --- Inflow Score (1-5) ---
            # Based on TAO and alpha inflow amounts
            tao_in_tao = tao_in / 1e9 if tao_in else 0
            alpha_in_norm = alpha_in / 1e9 if alpha_in else 0

            if tao_in_tao > 0.001:
                inflow_score = 5.0
                notes.append(f"⭐ TAO inflow detected: {tao_in_tao:.6f} τ/block — validators assign real value")
            elif tao_in_tao > 0:
                inflow_score = 4.0
                notes.append(f"TAO inflow: {tao_in_tao:.6f} τ/block")
            elif alpha_in_norm > 0.1:
                inflow_score = 3.5
                notes.append(f"Strong alpha inflow: {alpha_in_norm:.2f} α/block")
            elif alpha_in_norm > 0:
                inflow_score = 2.5
                notes.append(f"Minimal alpha inflow: {alpha_in_norm:.2f} α/block")
            else:
                inflow_score = 1.5
                notes.append("Zero TAO and alpha inflow — subnet not valued by root network")

            # --- Trend Score (1-5) ---
            # Compare to previous month's data
            if previous_data:
                prev_tao_in = previous_data.get("tao_in_emission_raw", 0)
                prev_alpha_in = previous_data.get("alpha_in_emission_raw", 0)

                tao_change = ((tao_in or 0) - prev_tao_in) / max(prev_tao_in, 1)
                alpha_change = ((alpha_in or 0) - prev_alpha_in) / max(prev_alpha_in, 1)

                if tao_change > 0.1 or alpha_change > 0.1:
                    trend_score = 4.0
                    notes.append(f"📈 Emission trending up (τ: {tao_change:+.1%}, α: {alpha_change:+.1%})")
                elif tao_change < -0.1 or alpha_change < -0.1:
                    trend_score = 2.0
                    notes.append(f"📉 Emission trending down (τ: {tao_change:+.1%}, α: {alpha_change:+.1%})")
                else:
                    trend_score = 3.0
                    notes.append("Emission stable month-over-month")
            else:
                trend_score = 3.0  # no prior data
                notes.append("No prior month data — trend neutral")

            # --- Composite Score ---
            # Rank: 40%, Inflow: 35%, Trend: 25%
            raw = (rank_score * 0.4 + inflow_score * 0.35 + trend_score * 0.25)
            # Normalize from 1-5 to 1-10
            total = min(10.0, max(1.0, raw * 2))

            details["tao_in_tao"] = tao_in_tao
            details["alpha_in_normalized"] = alpha_in_norm
            details["taostats_rank"] = taostats_rank

            return EmissionScore(
                total=round(total, 1),
                rank_score=round(rank_score, 1),
                inflow_score=round(inflow_score, 1),
                trend_score=round(trend_score, 1),
                details=details,
                notes=notes,
            )

    async def _safe_query(self, substrate, storage: str, params: list):
        """Safely query on-chain storage, returning None on error."""
        try:
            result = await substrate.query("SubtensorModule", storage, params)
            val = result.value if hasattr(result, 'value') else result
            return int(val) if val else 0
        except Exception:
            return 0


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EmissionMetrics Agent 🧮")
    parser.add_argument("--netuid", type=int, required=True, help="Subnet netuid")
    parser.add_argument("--rank", type=int, default=None, help="Pruning rank from taostats")
    parser.add_argument("--previous", type=str, default=None, help="Previous month data JSON")
    args = parser.parse_args()

    agent = EmissionMetricsAgent()
    result = agent.score(args.netuid, args.rank,
                         json.loads(args.previous) if args.previous else None)

    print(json.dumps({
        "score": result.total,
        "rank_score": result.rank_score,
        "inflow_score": result.inflow_score,
        "trend_score": result.trend_score,
        "details": result.details,
        "notes": result.notes,
    }, indent=2))
