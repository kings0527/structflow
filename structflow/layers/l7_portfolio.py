"""L7: Portfolio Layer (optional) — maps investment targets."""

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
    L7PortfolioMapping,
    ScanInput,
)

L7_PROMPT_TEMPLATE = """
Map investment targets for this industry based on the full structural analysis.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}

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

L6 Alpha:
- Consensus: {consensus}
- Reality: {reality}
- Mispricing: {mispricing}
- Alpha Thesis: {alpha_thesis}

You MUST map entities into THREE categories:

1. best_positioned_entities — Entities best positioned to profit from the structural reality
   and the alpha thesis. These entities have structural advantages that align with the
   identified mispricing. For each: name, role, reason (why they are best positioned).

2. overvalued_entities — Entities whose market value exceeds their structural value.
   These are entities that benefit from the market consensus/narrative but whose
   structural position is weaker than the market thinks. For each: name, role, reason.

3. fragile_entities — Entities that are structurally fragile to the bear scenario.
   These entities would suffer most if the bear scenario unfolds. For each: name, role, reason.

## Hard Rule
Each entity MUST include a concrete reason tied to the structural analysis (L0-L6),
not a generic statement like "strong company". Reference specific power dynamics,
flow positions, risk concentrations, or driver exposures.

Exclude entities that no longer exist independently (e.g., acquired/merged). Use the
search context to verify.

Use the provided real-world data to map actual companies based on current market conditions.

Output must be valid JSON matching the L7PortfolioMapping schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities[:5])
        lines.append(f"- {role.role_type}: {entities_str}")
    return "\n".join(lines)


def _build_drivers_summary(l4_result: L4DriverAnalysis) -> str:
    lines = []
    for d in l4_result.drivers:
        lines.append(f"  - {d.name}: importance={d.importance}, direction={d.direction}")
    return "\n".join(lines) if lines else "None identified"


def run_l7(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l3_result: L3RiskAnalysis,
    l4_result: L4DriverAnalysis,
    l5_result: L5ScenarioAnalysis,
    l6_result: L6AlphaAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L7PortfolioMapping:
    """Execute L7 portfolio mapping."""
    power = l1_result.power_matrix
    prompt = L7_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_elasticity=l0_result.demand_elasticity,
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
        consensus=l6_result.consensus,
        reality=l6_result.reality,
        mispricing=l6_result.mispricing,
        alpha_thesis=l6_result.alpha_thesis,
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L7PortfolioMapping, context_data=context_data, temperature=temperature)
