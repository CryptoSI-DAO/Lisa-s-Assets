# Lisa's Assets — Lisa Coefficient Optimization

## Objective
Improve the Lisa Coefficient scoring model for crypto project evaluation.

## Current Issues
1. **Formula inconsistency**: Published Lisa Coefficients deviate from the weighted-sum formula by 0.1-0.55 points across most TAO and ETH scorecards
2. **Missing agents**: 3 of 7 agents (HypePulse, CodeCrafter, RiskEye) have no Python implementation
3. **Bugs**: `stake_flow.py` queries `SubnetLimit` (global subnet count) instead of per-subnet validator count
4. **No tests**: Zero test coverage, no ground truth dataset
5. **Decoupled frontend**: `renderer.js` recomputes client-side from static JSON, ignoring the Python agents

## Architecture
- **7 agents** each output a 1-10 score with sub-scores and notes
- **Weights**: TruthSeeker 20%, MavenMetrics 20%, TokenLogic 15%, LiquidEdge 15%, HypePulse 10%, CodeCrafter 10%, RiskEye 10%
- **Lisa Coefficient** = weighted sum of all 7 scores (range 1-10)
- **Verdicts**: ≥8.0 Strong Hold · 6.0-7.9 Research Further · 4.0-5.9 Watch · 2.0-3.9 Caution · <2.0 Avoid

## Eval
Run `python eval.py` — returns a composite score (0-100).

Higher = better. The eval checks:
- Formula consistency (30%): does computed = published?
- Score range validity (20%): all scores in [1,10]?
- Agent completeness (20%): all 7 agents present?
- Weight coverage (30%): all canonical agent keys used?

## Data
- `data/subnets-may-2026.json` — 10 Bittensor subnets with 7 agent scores each
- `data/eth-ecosystem.json` — 7 ETH projects with 7 agent scores each
