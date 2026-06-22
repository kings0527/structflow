"""L3: Risk Layer — identifies true risk attribution and profit-risk separation."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowAnalysis,
    L3RiskAnalysis,
    ScanInput,
)

L3_PROMPT_TEMPLATE = """
Identify the true risk attribution in the following industry.

Industry: {industry}
Region: {region}

L0 Context:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}
- Narrative Dependency: {narrative_dependency}
- Regulatory Dependency: {regulatory_dependency}

L1 Roles:
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
- Information Flow: {info_flow_summary}
- Attention Flow: {attention_flow_summary}

You MUST output TWO things:

1. Risk Concentrations (risk_concentrations) — List every point where risk concentrates.
   For each: entity, risk_type (credit/operational/regulatory/market/liquidity), severity (0-1).
   Be specific: which entity bears which type of risk, and how severe.

2. Profit-Risk Separation (profit_risk_separation) — Analyze whether profit and risk are separated.
   - profit_owner: Who profits the most from this industry?
   - risk_owner: Who bears the most risk in this industry?
   - gap_score: 0 = profit and risk are aligned (same entity), 1 = fully separated (different entities)

## Hard Rule
You MUST answer these three questions explicitly:
- Who profits the most?
- Who bears the most risk?
- Are they the same entity?

If profit and risk are separated (gap_score > 0.5), this is a structural fragility —
someone is extracting profit without bearing proportional risk (moral hazard).

Use the provided real-world data to identify actual risk concentrations and profit-risk dynamics.

Output must be valid JSON matching the L3RiskAnalysis schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities_str}")
    return "\n".join(lines)


def _build_flow_summary(nodes, label: str) -> str:
    if not nodes:
        return f"No {label} nodes identified"
    return " -> ".join(n.entity for n in nodes)


def run_l3(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l2_result: L2FlowAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L3RiskAnalysis:
    """Execute L3 risk attribution analysis."""
    power = l1_result.power_matrix
    prompt = L3_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
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
        cash_flow_summary=_build_flow_summary(l2_result.cash_nodes, "cash"),
        risk_flow_summary=_build_flow_summary(l2_result.risk_nodes, "risk"),
        info_flow_summary=_build_flow_summary(l2_result.information_nodes, "information"),
        attention_flow_summary=_build_flow_summary(l2_result.attention_nodes, "attention"),
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L3RiskAnalysis, context_data=context_data, temperature=temperature)
