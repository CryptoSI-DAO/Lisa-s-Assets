#!/usr/bin/env python3
"""
SubnetEconomics Agent 📊
Scores TAO lockup, burn rate, and registration economics (1-10).

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
class EconomicsScore:
    total: float
    lockup_tao: float
    burn_raw: int
    has_commitment: bool  # non-zero lockup
    notes: list


class SubnetEconomicsAgent:
    async def _query(self, substrate, key, params=None):
        try:
            result = await substrate.query("SubtensorModule", key, params or [])
            val = result.value if hasattr(result, "value") else result
            return int(val) if val else 0
        except Exception:
            return 0

    async def score_async(self, netuid):
        notes = []
        locked = 0
        burn = 0

        if HAS_SUBSTRATE:
            try:
                async with AsyncSubstrateInterface(FINNEY_WSS) as sub:
                    locked = await self._query(sub, "SubnetLocked", [netuid])
                    burn = await self._query(sub, "Burn", [netuid])
            except Exception as e:
                notes.append(f"RPC failed: {e}")

        locked_tao = locked / 1e9
        has_commitment = locked_tao > 0

        # Scoring heuristic
        if locked_tao > 200:
            score = 4.5
            notes.append(f"Strong commitment: {locked_tao:,.0f} TAO locked")
        elif locked_tao > 50:
            score = 3.5
            notes.append(f"Moderate commitment: {locked_tao:,.0f} TAO locked")
        elif locked_tao > 0:
            score = 2.0
            notes.append(f"Minimal lockup: {locked_tao:,.0f} TAO")
        else:
            score = 1.0
            notes.append("Zero lockup — owner has no skin in the game")

        notes.append(f"Burn: {burn} RAO (min 500)")
        total = min(10.0, max(1.0, score * 2))
        return EconomicsScore(round(total, 1), locked_tao, burn, has_commitment, notes)

    def score(self, netuid):
        return asyncio.run(self.score_async(netuid))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="SubnetEconomics Agent 📊")
    p.add_argument("--netuid", type=int, required=True)
    a = p.parse_args()
    result = SubnetEconomicsAgent().score(a.netuid)
    print(json.dumps(asdict(result), indent=2, default=str))
