"""L1: Structure Layer — identifies roles and power matrix."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import L0IndustryDefinition, L1StructureDecomposition, ScanInput

L1_PROMPT_TEMPLATE = """
Decompose the structure of the following industry.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Context (already established):
- Core Need: {core_need}
- Substitution Risk: {substitution_risk}
- Demand Elasticity: {demand_elasticity}
- Narrative Dependency: {narrative_dependency}
- Regulatory Dependency: {regulatory_dependency}

{peer_section}

You MUST identify exactly FIVE roles in this industry:
1. Producer — who creates the product/service
2. Consumer — who pays for and uses it
3. Mediator — who connects producer and consumer (platforms, distributors, brokers)
4. Controller — who sets rules, standards, or controls access
5. Capital Provider — who controls capital flow (banks, VCs, PE, sovereign funds, bondholders)

For each role, list the specific entities (companies, organizations) playing it.
Each role MUST include an `evidence` field — structural evidence backing the assignment.
Example: "controls 80% of global refining capacity" NOT "is a major player".

You MUST also output a Power Matrix with these five dimensions.
Each dimension MUST be attributed to a specific role — never write vague statements like "the platform is strong".
Instead write: "Controller dominates pricing_power via exclusive access to X resource".

Power Matrix dimensions:
- pricing_power: Who decides price?
- entry_power: Who controls entry barriers?
- standard_power: Who defines industry standards?
- capital_power: Who controls capital allocation and flow?
- data_power: Who controls information and data?

## Hard Rule
EVERY conclusion must bind to evidence. Forbidden: "Company A is strong".
Required: "Company A controls 80% of distribution channels" — quantify, specify mechanism.

Use the provided real-world data to identify actual companies and their roles based on current market data.

Output must be valid JSON matching the L1StructureDecomposition schema.
"""


def _build_peer_section(peer_set: list[str]) -> str:
    if not peer_set:
        return ""
    return "Key companies to analyze: " + ", ".join(peer_set)


def run_l1(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: L0IndustryDefinition,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L1StructureDecomposition:
    """Execute L1 structure decomposition."""
    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_elasticity=l0_result.demand_elasticity,
        narrative_dependency=l0_result.narrative_dependency,
        regulatory_dependency=l0_result.regulatory_dependency,
        peer_section=_build_peer_section(scan_input.peer_set),
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L1StructureDecomposition, context_data=context_data, temperature=temperature)
