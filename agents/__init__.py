"""Lisa's Assets — Subnet Scoring Agents

Seven AI agents score Bittensor subnets on different dimensions.
Each returns a 1-10 score synthesized by SubnetRisk into the Lisa Coefficient.

Agents:
    EmissionMetricsAgent  🧮  Emission inflow, rank, trend     (20%)
    SubnetOracleAgent     🔍  Purpose, team, product, moat     (20%)
    StakeFlowAgent        💧  TAO staking, validators, dist.   (15%)
    SubnetEconomicsAgent  📊  Lockup, burn, α/τ ratio         (15%)
    HypePulseAgent        🔥  Discord, Twitter, sentiment       (10%)
    CodeCrafterAgent      👨‍💻  GitHub activity, code quality      (10%)
    RiskEyeAgent          ⚠️  Risk profiling → Lisa Coefficient   (10%)
"""

from .emission_metrics import EmissionMetricsAgent
from .subnet_oracle import SubnetOracleAgent
from .subnet_economics import SubnetEconomicsAgent
from .stake_flow import StakeFlowAgent
from .hype_pulse import HypePulseAgent
from .code_crafter import CodeCrafterAgent
from .risk_eye import RiskEyeAgent

__all__ = [
    "EmissionMetricsAgent",
    "SubnetOracleAgent",
    "SubnetEconomicsAgent",
    "StakeFlowAgent",
    "HypePulseAgent",
    "CodeCrafterAgent",
    "RiskEyeAgent",
]
