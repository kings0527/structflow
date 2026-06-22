"""L1: Structure Decomposition Layer — identifies roles and power matrix."""

from __future__ import annotations

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
- Demand Stability: {demand_stability}
- Narrative Dependency: {narrative_dependency}

{peer_section}

You MUST identify exactly four roles in this industry:
1. Producer — who creates the product/service
2. Payer — who pays for it
3. Mediator — who connects producer and payer (platforms, distributors, brokers)
4. Controller — who sets rules, standards, or controls access

For each role, list the specific entities (companies, organizations) playing it.

You MUST also output a Power Matrix with these five dimensions. Each dimension MUST be attributed to a specific role — never write vague statements like "the platform is strong". Instead write: "Controller dominates pricing_power via X mechanism".

Power Matrix dimensions:
- pricing_power: Who decides price?
- entry_control: Who controls entry barriers?
- data_control: Who controls information?
- switching_cost: What makes it hard for users to leave?
- standard_control: Who defines industry standards?

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
) -> L1StructureDecomposition:
    """Execute L1 structure decomposition."""
    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        core_need=l0_result.core_need,
        substitution_risk=l0_result.substitution_risk,
        demand_stability=l0_result.demand_stability,
        narrative_dependency=l0_result.narrative_dependency,
        peer_section=_build_peer_section(scan_input.peer_set),
    )
    return client.structured_call(prompt, L1StructureDecomposition)
