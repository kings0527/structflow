"""L4: Driver Layer — finds industry driver factors."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowAnalysis,
    L3RiskAnalysis,
    L4DriverAnalysis,
    ScanInput,
)

L4_PROMPT_TEMPLATE = """
Find the key driver factors that determine the trajectory of this industry.

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
- Entry Power: {entry_power}
- Standard Power: {standard_power}
- Capital Power: {capital_power}
- Data Power: {data_power}

L2 Flow Summary:
- Cash Flow: {cash_flow_summary}
- Risk Flow: {risk_flow_summary}
- Attention Flow: {attention_flow_summary}

L3 Risk:
- Risk Concentrations: {risk_concentrations}
- Profit Owner: {profit_owner}
- Risk Owner: {risk_owner}
- Gap Score: {gap_score}

You MUST identify the industry's key driver factors — the variables that will determine
this industry's future trajectory. These are NOT descriptions of the current state,
but the FACTORS that will drive change.

For each driver, output:
- name: The driver factor name (e.g., "Real Interest Rate", "Central Bank Buying", "ETF Flows")
- importance: Weight of this driver (0-1). ALL drivers' importance MUST sum to 1.0 (100%).
- direction: "+" (positive for industry) or "-" (negative for industry)
- confidence: How confident are you in this assessment (0-1)

## Hard Rule
The sum of ALL drivers' importance values MUST equal 1.0 (100%).
This is non-negotiable — if you list 5 drivers, their importances must sum to exactly 1.0.

Think like an investor: what variables, if they change, would most impact this industry?
Prioritize structural drivers over narrative drivers.

Use the provided real-world data to identify actual market drivers based on current conditions.

Output must be valid JSON matching the L4DriverAnalysis schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities_str}")
    return "\n".join(lines)


def _build_flow_summary(nodes) -> str:
    if not nodes:
        return "N/A"
    return " -> ".join(n.entity for n in nodes)


def _build_risk_summary(l3_result: L3RiskAnalysis) -> str:
    lines = []
    for rc in l3_result.risk_concentrations:
        lines.append(f"  - {rc.entity}: {rc.risk_type} (severity={rc.severity})")
    return "\n".join(lines) if lines else "None identified"


def run_l4(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l2_result: L2FlowAnalysis,
    l3_result: L3RiskAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L4DriverAnalysis:
    """Execute L4 driver analysis."""
    power = l1_result.power_matrix
    prompt = L4_PROMPT_TEMPLATE.format(
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
        entry_power=power.entry_power,
        standard_power=power.standard_power,
        capital_power=power.capital_power,
        data_power=power.data_power,
        cash_flow_summary=_build_flow_summary(l2_result.cash_nodes),
        risk_flow_summary=_build_flow_summary(l2_result.risk_nodes),
        attention_flow_summary=_build_flow_summary(l2_result.attention_nodes),
        risk_concentrations=_build_risk_summary(l3_result),
        profit_owner=l3_result.profit_risk_separation.profit_owner,
        risk_owner=l3_result.profit_risk_separation.risk_owner,
        gap_score=l3_result.profit_risk_separation.gap_score,
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L4DriverAnalysis, context_data=context_data, temperature=temperature)
