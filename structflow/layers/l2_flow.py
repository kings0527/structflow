"""L2: Flow Layer — traces cash, information, risk, and attention flows."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    L0IndustryDefinition,
    L1StructureDecomposition,
    L2FlowAnalysis,
    ScanInput,
)

L2_PROMPT_TEMPLATE = """
Trace ALL flows in the following industry.

Industry: {industry}
Region: {region}

L0 Context:
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}
- Narrative Dependency: {narrative_dependency}
- Regulatory Dependency: {regulatory_dependency}

L1 Context (roles identified):
{roles_summary}

L1 Power Matrix:
- Pricing Power: {pricing_power}
- Entry Power: {entry_power}
- Standard Power: {standard_power}
- Capital Power: {capital_power}
- Data Power: {data_power}

You MUST trace FOUR flows completely:

1. Cash Flow (cash_nodes) — How does money move from consumer to final recipient? List every node.
   Include: payment paths, revenue capture, cost pass-through, hidden transfers.

2. Information Flow (information_nodes) — Who knows what first? Who is delayed? Where is information asymmetry?
   Include: data monopolies, information advantages, transparency gaps, insider knowledge.

3. Risk Flow (risk_nodes) — Where does risk flow and accumulate? Who bears it? Who passes it on?
   Include: risk transfer chains, concentration points, tail risk holders.

4. Attention Flow (attention_nodes) — How does attention drive cash flow in this industry?
   Include: who captures attention, how attention converts to revenue, attention bottlenecks.
   This is critical: in many modern industries, attention determines cash flow.

For each flow, output a list of FlowNode objects with: entity, role, description.

## Hard Rule
ALL FOUR flows must be present and substantive. An industry cannot lack any of these flows —
if attention seems irrelevant, dig deeper (e.g., regulatory attention, investor attention, media attention).

Use the provided real-world data to trace actual flows based on current market conditions.

Output must be valid JSON matching the L2FlowAnalysis schema.
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
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L2FlowAnalysis:
    """Execute L2 flow analysis."""
    power = l1_result.power_matrix
    prompt = L2_PROMPT_TEMPLATE.format(
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
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L2FlowAnalysis, context_data=context_data, temperature=temperature)
