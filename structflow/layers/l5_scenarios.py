"""L5: Scenario Layer — counterfactual reasoning with Bull/Base/Bear scenarios."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L3RiskAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    ScanInput,
)

L5_PROMPT_TEMPLATE = """
Perform counterfactual reasoning on this industry — construct three scenarios.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}
- Regulatory Dependency: {regulatory_dependency}

L3 Risk:
- Profit Owner: {profit_owner}
- Risk Owner: {risk_owner}
- Gap Score: {gap_score}

L4 Drivers:
{drivers_summary}

You MUST construct THREE scenarios:

1. Bull (bull) — The most optimistic realistic scenario.
   What would need to happen for this industry to significantly outperform expectations?

2. Base (base) — The most likely scenario.
   What is the most probable outcome given current structural conditions?

3. Bear (bear) — The most pessimistic realistic scenario.
   What would need to happen for this industry to significantly underperform?

For each scenario, output:
- probability: Likelihood of this scenario (0-1).
  ALL THREE probabilities MUST sum to 1.0 (100%).
- triggers: List of specific events or conditions that would trigger this scenario.
  Be concrete: "Fed cuts rates by 50bp", "New regulation bans X", etc.

## Hard Rule
The sum of bull.probability + base.probability + bear.probability MUST equal 1.0 (100%).
This is non-negotiable.

Think like a strategist: what are the branching points? What signals would indicate
which scenario is unfolding?

Use the provided real-world data to ground scenarios in actual market conditions.

Output must be valid JSON matching the L5ScenarioAnalysis schema.
"""


def _build_drivers_summary(l4_result: L4DriverAnalysis) -> str:
    lines = []
    for d in l4_result.drivers:
        lines.append(f"  - {d.name}: importance={d.importance}, direction={d.direction}, confidence={d.confidence}")
    return "\n".join(lines) if lines else "None identified"


def run_l5(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l3_result: L3RiskAnalysis,
    l4_result: L4DriverAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L5ScenarioAnalysis:
    """Execute L5 scenario analysis."""
    prompt = L5_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_elasticity=l0_result.demand_elasticity,
        regulatory_dependency=l0_result.regulatory_dependency,
        profit_owner=l3_result.profit_risk_separation.profit_owner,
        risk_owner=l3_result.profit_risk_separation.risk_owner,
        gap_score=l3_result.profit_risk_separation.gap_score,
        drivers_summary=_build_drivers_summary(l4_result),
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L5ScenarioAnalysis, context_data=context_data, temperature=temperature)
