"""L6: Alpha Layer — discovers market mispricing (CORE VALUE of V2).

This is the most important V2 upgrade. The goal is NOT to describe the industry,
but to discover the gap between market narrative and structural reality,
and quantify the opportunity this gap creates.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L3RiskAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    L6AlphaAnalysis,
    ScanInput,
)

L6_PROMPT_TEMPLATE = """
Discover the market mispricing in this industry.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}
- Narrative Dependency: {narrative_dependency}
- Regulatory Dependency: {regulatory_dependency}

L1 Structure:
{roles_summary}

L1 Power Matrix:
- Pricing Power: {pricing_power}
- Capital Power: {capital_power}
- Data Power: {data_power}

L3 Risk:
- Profit Owner: {profit_owner}
- Risk Owner: {risk_owner}
- Gap Score: {gap_score}

L4 Drivers:
{drivers_summary}

L5 Scenarios:
- Bull (prob={bull_prob}): {bull_triggers}
- Base (prob={base_prob}): {base_triggers}
- Bear (prob={bear_prob}): {bear_triggers}

You are a Structural Alpha Discovery Engine. Your task is to find where the market
is WRONG about this industry — where market narrative diverges from structural reality.

You MUST output FOUR fields:

1. consensus: What does the market currently believe about this industry?
   This is the dominant narrative — what most investors think.
   Example: "Gold rises because of safe-haven demand during crises"

2. reality: What does the STRUCTURE actually show?
   This is what the L0-L5 analysis reveals — the structural truth.
   Example: "Central bank buying accounts for primary demand increment, not crisis hedging"

3. mispricing: Where specifically is the market wrong?
   Identify the exact gap between consensus and reality.
   Example: "Market underestimates the persistence of central bank gold purchases"

4. alpha_thesis: How to profit from this mispricing?
   Convert the mispricing into an actionable investment thesis.
   Example: "Long gold and gold producers — structural demand from central banks is persistent and underestimated"

## Hard Rule
You MUST output the contrast: "market thinks X" vs "structure shows Y".
If there is no mispricing (consensus = reality), say so explicitly — but dig deeper,
because markets are rarely perfectly priced relative to structural reality.

This is the core value of the entire system:
> Discover the gap between market narrative and structural reality,
> and quantify the opportunity this gap creates.

Use the provided real-world data to identify actual market consensus and structural reality.

Output must be valid JSON matching the L6AlphaAnalysis schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities_str}")
    return "\n".join(lines)


def _build_drivers_summary(l4_result: L4DriverAnalysis) -> str:
    lines = []
    for d in l4_result.drivers:
        lines.append(f"  - {d.name}: importance={d.importance}, direction={d.direction}")
    return "\n".join(lines) if lines else "None identified"


def run_l6(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l3_result: L3RiskAnalysis,
    l4_result: L4DriverAnalysis,
    l5_result: L5ScenarioAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L6AlphaAnalysis:
    """Execute L6 alpha discovery analysis."""
    power = l1_result.power_matrix
    prompt = L6_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_elasticity=l0_result.demand_elasticity,
        narrative_dependency=l0_result.narrative_dependency,
        regulatory_dependency=l0_result.regulatory_dependency,
        roles_summary=_build_roles_summary(l1_result),
        pricing_power=power.pricing_power,
        capital_power=power.capital_power,
        data_power=power.data_power,
        profit_owner=l3_result.profit_risk_separation.profit_owner,
        risk_owner=l3_result.profit_risk_separation.risk_owner,
        gap_score=l3_result.profit_risk_separation.gap_score,
        drivers_summary=_build_drivers_summary(l4_result),
        bull_prob=l5_result.bull.probability,
        bull_triggers="; ".join(l5_result.bull.triggers),
        base_prob=l5_result.base.probability,
        base_triggers="; ".join(l5_result.base.triggers),
        bear_prob=l5_result.bear.probability,
        bear_triggers="; ".join(l5_result.bear.triggers),
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L6AlphaAnalysis, context_data=context_data, temperature=temperature)
