# 🎯 Subnet Scorecards

> Bittensor subnet analysis scored by the Lisa Coefficient framework.
> Each subnet is evaluated by 7 specialized agents, synthesized into a final Lisa Coefficient score (1-10).

## Latest Report

**May 2026** → [scorecards/may-2026.md](scorecards/may-2026.md)

## Top Subnets — May 2026

| Rank | Subnet | Name | Lisa Coefficient | Verdict |
|------|--------|------|-----------------|---------|
| 1 | SN116 | TaoLend | 🔷 6.5 | Research Further |
| 2 | SN80 | Dogelayer | 🔷 7.8 | **Hold / Conviction** |
| 3 | SN40 | Chunking | 🔷 2.6 | Avoid |
| 4 | SN58 | (Pending) | 🔷 1.2 | Avoid |
| 5 | SN72 | StreetVision | 🔷 6.2 | Research Further |
| 6 | SN92 | TensorClaw | 🔷 7.2 | **Watch** |
| 7 | SN42 | Unknown | 🔷 1.0 | Avoid |
| 8 | SN89 | InfiniteHash | 🔷 6.8 | Research Further |
| 9 | SN86 | (Unnamed) | 🔷 1.0 | Avoid |
| 10 | SN111 | oneoneone | 🔷 1.6 | Avoid |

## Repo Structure

```
├── agents/                  # Scoring agent scripts
│   ├── emission_metrics.py  # MavenMetrics → EmissionMetrics
│   ├── subnet_economics.py  # TokenLogic → SubnetEconomics
│   ├── onchain_chad.py      # CodeCrafter → OnChainChad
│   ├── subnet_hype.py       # HypePulse → SubnetHype
│   ├── subnet_oracle.py     # TruthSeeker → SubnetOracle
│   ├── stake_flow.py        # LiquidEdge → StakeFlow
│   └── subnet_risk.py       # RiskEye → SubnetRisk (synthesizes Lisa Coefficient)
├── scorecards/              # Generated scorecard reports
│   └── may-2026.md
├── templates/               # Scorecard templates
│   └── scorecard-template.md
├── data/                    # Scraped on-chain data
│   └── may-2026/
├── website/                 # Static website for scorecards
│   └── index.html
└── README.md
```

## The 7 Agents

| Agent | Emoji | Role | What It Measures |
|-------|-------|------|-----------------|
| **EmissionMetrics** | 🧮 | Emission Analyst | Daily emission, TAO/α inflow, emission trend, pruning rank |
| **SubnetEconomics** | 📊 | Subnet Economist | Lockup, burn, α/τ ratio, recycling, registration cost |
| **OnChainChad** | 👨‍💻 | Code & Dev Auditor | GitHub activity, code quality, open source presence |
| **SubnetHype** | 🔥 | Community Tracker | Discord, Twitter, social sentiment, organic growth |
| **SubnetOracle** | 🔍 | Fundamentals Investigator | Use case, team, partnerships, real-world utility |
| **StakeFlow** | 💧 | Staking Analyst | TAO staking, validator count, stake distribution |
| **SubnetRisk** | ⚠️ | Risk Profiler | Synthesizes all agents → Lisa Coefficient (1-10) |

## Scoring Methodology

Each agent scores 1–10. The SubnetRisk agent synthesizes with weighted aggregation:

```
Lisa Coefficient = (
    EmissionMetrics × 0.20 +
    SubnetEconomics × 0.15 +
    OnChainChad × 0.10 +
    SubnetHype × 0.10 +
    SubnetOracle × 0.20 +
    StakeFlow × 0.15 +
    RiskProfile × 0.10
)
```

## Verdict Scale

| Score | Verdict | Action |
|-------|---------|--------|
| 8.0–10.0 | 🟢 **Strong Hold** | High conviction — monitor closely |
| 6.0–7.9 | 🔷 **Research Further** | Interesting — deep dive recommended |
| 4.0–5.9 | 🟡 **Watch** | Wait for more data |
| 2.0–3.9 | 🟠 **Caution** | High risk, limited fundamentals |
| 1.0–1.9 | 🔴 **Avoid** | No fundamentals, emission-only play |

---

*Built with 💜 by the Lisa's Assets framework. Scorecards auto-generated monthly.*
