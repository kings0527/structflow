"""L2: Flow & Risk Layer — traces cash, information, and risk flows."""

from __future__ import annotations

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowRiskAnalysis,
    ScanInput,
)

L2_PROMPT_TEMPLATE = """
Trace all flows in the following industry.

Industry: {industry}
Region: {region}

L0 Context:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Stability: {demand_stability}

L1 Context (roles identified):
{roles_summary}

L1 Power Matrix:
- Pricing Power: {pricing_power}
- Entry Control: {entry_control}
- Data Control: {data_control}
- Switching Cost: {switching_cost}
- Standard Control: {standard_control}

You MUST trace three flows completely:

1. Cash Flow — How does money move from payer to final recipient? List every node.
2. Information Flow — Who knows what first? Who is delayed? Where is information asymmetry?
3. Risk Flow — Where does risk accumulate? Who bears it? Is profit separated from risk?

For each flow, output a chain of FlowNode objects with: entity, role, description.

You MUST also answer these three mandatory questions:
- subsidy_answer: Who is continuously subsidizing the system? (If nobody, explain why the system is self-sustaining)
- risk_concentration_answer: Where does risk ultimately concentrate?
- profit_risk_separation_answer: Is profit separated from risk? Who profits without bearing risk?

Additionally identify:
- value_capture_points: Where in the chain is value actually captured (not just passed through)?
- hidden_subsidy_sources: Any hidden subsidies (government, cross-subsidy, data monetization, etc.)

Output must be valid JSON matching the L2FlowRiskAnalysis schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities_str} — {role.description}")
    return "\n".join(lines)


def run_l2(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
) -> L2FlowRiskAnalysis:
    """Execute L2 flow and risk analysis."""
    power = l1_result.power_matrix
    prompt = L2_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_stability=l0_result.demand_stability,
        roles_summary=_build_roles_summary(l1_result),
        pricing_power=power.pricing_power,
        entry_control=power.entry_control,
        data_control=power.data_control,
        switching_cost=power.switching_cost,
        standard_control=power.standard_control,
    )
    return client.structured_call(prompt, L2FlowRiskAnalysis)
