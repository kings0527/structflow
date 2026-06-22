"""L3: Scoring & Ranking Layer — produces score vectors and structural phase."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowRiskAnalysis,
    L3ScoringRanking,
    ScanInput,
)

L3_PROMPT_TEMPLATE = """
Score and rank the following industry and its key companies.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Context:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Stability: {demand_stability}
- Narrative Dependency: {narrative_dependency}

L1 Roles:
{roles_summary}

L1 Power Matrix:
- Pricing Power: {pricing_power}
- Entry Control: {entry_control}
- Data Control: {data_control}
- Switching Cost: {switching_cost}
- Standard Control: {standard_control}

L2 Flow Summary:
- Cash Flow Chain: {cash_flow_summary}
- Risk Concentration: {risk_concentration}
- Profit-Risk Separation: {profit_risk_separation}
- Hidden Subsidies: {hidden_subsidies}

{peer_section}

You MUST output:

1. Industry Score Vector (S Vector) — score the overall industry on 5 dimensions (0-10 each):
   - control_score: How concentrated is control?
   - profit_capture_score: How well does the industry capture value?
   - risk_displacement_score: How well does the industry displace risk to outsiders?
   - information_advantage_score: How much information asymmetry exists?
   - incentive_alignment_score: How aligned are incentives with value creation?

2. Company Rankings — for each key company, output:
   - name, role
   - score_vector (same 5 dimensions)
   - structural_health = (control_score × profit_capture_score × information_advantage_score) ÷ (risk_displacement_score + (10 - incentive_alignment_score))
     Note: higher risk_displacement means risk is pushed to others (good for the company), lower incentive_alignment means distortion (bad).

3. Structural Phase — identify which phase the industry is in:
   - emergent | growth | mature | decline | disrupted
   - List the reasoning signals that support your identification.

Use the provided real-world data to ground scores in actual financial performance, market share, and competitive dynamics.

Output must be valid JSON matching the L3ScoringRanking schema.
"""


def _build_roles_summary(l1_result: L1StructureDecomposition) -> str:
    lines = []
    for role in l1_result.roles:
        entities_str = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities_str}")
    return "\n".join(lines)


def _build_cash_flow_summary(l2_result: L2FlowRiskAnalysis) -> str:
    return " → ".join(node.entity for node in l2_result.cash_flow_chain)


def _build_hidden_subsidies_summary(l2_result: L2FlowRiskAnalysis) -> str:
    if not l2_result.hidden_subsidy_sources:
        return "None identified"
    return "; ".join(node.description for node in l2_result.hidden_subsidy_sources)


def run_l3(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    l1_result: L1StructureDecomposition,
    l2_result: L2FlowRiskAnalysis,
    context_data: Optional[str] = None,
) -> L3ScoringRanking:
    """Execute L3 scoring and ranking."""
    power = l1_result.power_matrix
    peer_section = ""
    if scan_input.peer_set:
        peer_section = "Companies to score: " + ", ".join(scan_input.peer_set)

    prompt = L3_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_stability=l0_result.demand_stability,
        narrative_dependency=l0_result.narrative_dependency,
        roles_summary=_build_roles_summary(l1_result),
        pricing_power=power.pricing_power,
        entry_control=power.entry_control,
        data_control=power.data_control,
        switching_cost=power.switching_cost,
        standard_control=power.standard_control,
        cash_flow_summary=_build_cash_flow_summary(l2_result),
        risk_concentration=l2_result.risk_concentration_answer,
        profit_risk_separation=l2_result.profit_risk_separation_answer,
        hidden_subsidies=_build_hidden_subsidies_summary(l2_result),
        peer_section=peer_section,
    )
    return client.structured_call(prompt, L3ScoringRanking, context_data=context_data)
