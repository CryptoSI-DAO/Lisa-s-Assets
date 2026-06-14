#!/usr/bin/env python3
"""
StakeFlow Agent 💧
Scores TAO staking, validator count, and stake distribution (1-10).

Weight in Lisa Coefficient: 15%
"""

import asyncio
import json
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from async_substrate_interface import AsyncSubstrateInterface
    HAS_SUBSTRATE = True
except ImportError:
    HAS_SUBSTRATE = False

FINNEY_WSS = "wss://entrypoint-finney.opentensor.ai:443"


@dataclass
class StakeFlowScore:
    total: float
    validator_count: int
    total_stake_tao: float
    stake_distribution: str  # "balanced", "concentrated", "unknown"
    notes: list


class StakeFlowAgent:
    async def _query(self, substrate, key, params=None):
        try:
            result = await substrate.query("SubtensorModule", key, params or [])
            val = result.value if hasattr(result, "value") else result
            return int(val) if val else 0
        except Exception:
            return 0

    async def score_async(self, netuid):
        notes = []
        validators = 0
        total_stake = 0

        if HAS_SUBSTRATE:
            try:
                async with AsyncSubstrateInterface(FINNEY_WSS) as sub:
                    # SubnetworkN gives the per-subnet neuron/validator count
                    # TotalStake gives total TAO staked in the subnet
                    validators = await self._query(sub, "SubnetworkN", [netuid])
                    # Try to get total stake from root network
                    total_stake = await self._query(sub, "TotalStake", [])
            except Exception as e:
                notes.append(f"RPC failed: {e}")

        # Score heuristic based on validator count
        if validators >= 200:
            v_score, dist = 4.0, "healthy"
        elif validators >= 100:
            v_score, dist = 3.0, "growing"
        elif validators >= 50:
            v_score, dist = 2.0, "nascent"
        else:
            v_score, dist = 1.0, "thin"

        notes.append(f"{validators} validators — distribution: {dist}")
        if total_stake > 0:
            notes.append(f"Total network stake: {total_stake / 1e9:.0f} TAO")

        # Normalize 1-5 → 1-10
        total = min(10.0, max(1.0, v_score * 2))
        return StakeFlowScore(round(total, 1), validators, total_stake / 1e9, dist, notes)

    def score(self, netuid):
        return asyncio.run(self.score_async(netuid))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="StakeFlow Agent 💧")
    p.add_argument("--netuid", type=int, required=True)
    a = p.parse_args()
    result = StakeFlowAgent().score(a.netuid)
    print(json.dumps(asdict(result), indent=2, default=str))
