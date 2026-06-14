#!/usr/bin/env python3
"""
SubnetOracle Agent 🔍
Part of the Lisa's Assets Subnet Scoring Framework.

Evaluates a Bittensor subnet's fundamentals on a 1-1-10 scale.
Assesses: purpose, use case, team, partnerships, real-world utility.

Uses on-chain identity data (SubnetIdentitiesV3) and web scraping.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional

try:
    from async_substrate_interface import AsyncSubstrateInterface
    HAS_SUBSTRATE = True
except ImportError:
    HAS_SUBSTRATE = False

FINNEY_WSS = "wss://entrypoint-finney.opentensor.ai:443"


@dataclass
class OracleScore:
    total: float  # 1-10
    purpose_score: float
    team_score: float
    product_score: float
    moat_score: float
    details: dict
    notes: list[str]


KNOWN_SUBNETS = {
    # Pre-researched subnet data — updated monthly
    # Format: netuid: {name, purpose, team_known, product_stage, moat_description}
    80: {
        "name": "Dogelayer",
        "purpose": "Bridges Scrypt miners (LTC/DOGE) to Bittensor via merged mining",
        "team_known": True,
        "product_stage": "Live — operational mining pool with dual rewards",
        "moat": "Real mining infrastructure, AWS backend, open-source codebase",
        "website": "https://dogelayer.ai",
        "github": "https://github.com/dogelayer-ai/dogelayer",
    },
    92: {
        "name": "TensorClaw",
        "purpose": "Decentralized LLM inference — aggregates OpenAI/DeepSeek/Claude/Llama APIs",
        "team_known": False,
        "product_stage": "Active development — Business API launching",
        "moat": "Novel Business API model routes real commercial traffic to miners",
        "website": "https://tensorclaw.ai",
        "github": "https://github.com/tensorclaw/tensorclaw",
    },
    116: {
        "name": "TaoLend",
        "purpose": "Decentralized lending protocol for TAO and subnet alpha tokens",
        "team_known": False,
        "product_stage": "Pre-launch — website live, app in development",
        "moat": "First-mover in TAO-specific DeFi lending",
        "website": "https://taolend.io",
        "github": "https://github.com/xpenlab/taolend",
    },
    72: {
        "name": "StreetVision",
        "purpose": "Physical AI / roadwork detection using NATIX camera network",
        "team_known": True,
        "product_stage": "Live — active mining with HuggingFace model submissions",
        "moat": "Real camera network hardware, 1046+ commits, MIT licensed",
        "website": "https://www.natix.network",
        "github": "https://github.com/natixnetwork/streetvision-subnet",
    },
    89: {
        "name": "InfiniteHash",
        "purpose": "BTC mining pool bridged to Bittensor + Lightning Network",
        "team_known": False,
        "product_stage": "Early — concept proven, needs adoption",
        "moat": "BTC hashrate is largest decentralized compute network",
        "website": "https://infinitehash.xyz",
        "github": "https://github.com/backend-developers-ltd/InfiniteHash",
    },
    40: {
        "name": "Chunking",
        "purpose": "Text chunking for LLM/RAG pipelines",
        "team_known": False,
        "product_stage": "Live — functional but commoditized",
        "moat": "None — fully replicable by any LLM framework",
        "github": "https://github.com/VectorChat/chunking_subnet",
    },
}


class SubnetOracleAgent:
    def score(self, netuid: int, on_chain_identity: Optional[dict] = None) -> OracleScore:
        return asyncio.run(self._score_async(netuid, on_chain_identity))

    async def _score_async(self, netuid: int, on_chain_identity: Optional[dict] = None) -> OracleScore:
        notes = []
        known = KNOWN_SUBNETS.get(netuid)

        # Try on-chain identity first
        identity_name = None
        identity_desc = None
        if on_chain_identity:
            identity_name = on_chain_identity.get("subnet_name", "")
            identity_desc = on_chain_identity.get("description", "")

        # --- Purpose Score (1-5) ---
        if known and known["moat"] != "None — fully replicable by any LLM framework":
            purpose_score = 4.0
            notes.append(f"High-value purpose: {known['purpose'][:80]}")
            if known["moat"]:
                notes.append(f"Defensibility: {known['moat'][:80]}")
        elif known:
            purpose_score = 2.0
            notes.append(f"Commoditized purpose: {known['purpose'][:80]}")
        elif identity_name and identity_name not in ["Unknown", "Pending", ""]:
            purpose_score = 3.0
            notes.append(f"On-chain identity: {identity_name}")
            if identity_desc:
                notes.append(f"Description: {identity_desc[:100]}")
        else:
            purpose_score = 1.0
            notes.append("No identity or purpose found — cannot assess utility")

        # --- Team Score (1-5) ---
        if known and known["team_known"]:
            team_score = 4.0
            notes.append(f"Known team with public presence: {known.get('website', 'N/A')}")
        elif known and known.get("github"):
            team_score = 3.0
            notes.append(f"Open source (GitHub): {known['github']}")
        elif identity_name:
            team_score = 2.0
            notes.append(f"Anonymous team — only on-chain identity: {identity_name}")
        else:
            team_score = 1.0
            notes.append("No team information available")

        # --- Product Score (1-5) ---
        if known:
            stage = known["product_stage"].lower()
            if "live" in stage and "operational" in stage:
                product_score = 5.0
                notes.append("Live operational product")
            elif "live" in stage:
                product_score = 4.0
                notes.append("Live product")
            elif "active development" in stage or "launching" in stage:
                product_score = 3.5
                notes.append("Active development — product launching")
            elif "pre-launch" in stage or "early" in stage:
                product_score = 2.5
                notes.append("Pre-launch / early stage")
            else:
                product_score = 2.0
                notes.append(f"Stage: {known['product_stage']}")
        else:
            product_score = 1.5
            notes.append("Product stage unknown")

        # --- Moat Score (1-5) ---
        if known and "None" in known.get("moat", ""):
            moat_score = 1.0
            notes.append("No competitive moat — commodity service")
        elif known and any(w in known.get("moat", "").lower() for w in ["real", "infrastructure", "hardware", "network"]):
            moat_score = 4.5
            notes.append(f"Strong moat: {known['moat'][:80]}")
        elif known:
            moat_score = 3.0
            notes.append(f"Moderate moat: {known['moat'][:80]}")
        else:
            moat_score = 1.0
            notes.append("Moat unknown")

        # --- Composite ---
        raw = (purpose_score + team_score + product_score + moat_score) / 4
        total = min(10.0, max(1.0, raw * 2))

        return OracleScore(
            total=round(total, 1),
            purpose_score=round(purpose_score, 1),
            team_score=round(team_score, 1),
            product_score=round(product_score, 1),
            moat_score=round(moat_score, 1),
            details={"netuid": netuid, "name": known["name"] if known else identity_name},
            notes=notes,
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SubnetOracle Agent 🔍")
    parser.add_argument("--netuid", type=int, required=True)
    parser.add_argument("--identity", type=str, default=None, help="On-chain identity JSON")
    args = parser.parse_args()

    agent = SubnetOracleAgent()
    result = agent.score(args.netuid, json.loads(args.identity) if args.identity else None)

    print(json.dumps({
        "score": result.total,
        "purpose": result.purpose_score,
        "team": result.team_score,
        "product": result.product_score,
        "moat": result.moat_score,
        "notes": result.notes,
    }, indent=2))
