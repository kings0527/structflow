"""L7: Portfolio Layer (optional) — investment mapping.

Maps variable roles to specific investment entities.
Uses variable analysis from L0-L6, not industry-specific roles.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaSignal,
    DistortionAnalysis,
    DriverSet,
    L7PortfolioMapping,
    MetaSystemDefinition,
    RegimeState,
    ScanInput,
    VariableMapping,
)

L7_PROMPT_TEMPLATE = """
Map investment targets based on the variable analysis.

System: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}

L1 Variable Mapping:
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

L3 Drivers:
{drivers_summary}

L4 Regime: {current_regime} (confidence: {regime_confidence})

L5 Distortion: {market_belief} vs {true_drivers} (score: {distortion_score})

L6 Alpha: {alpha_signal} (confidence: {alpha_confidence})

Based on the variable analysis above, map specific entities (companies, assets, instruments)
to investment categories.

You MUST output a JSON object with exactly these fields:

1. best_positioned_entities: Entities best positioned to profit from the identified alpha.
   Each entity must have:
   - name: Entity name
   - role: Variable role (e.g., "SV controller", "CV manipulator", "FV bottleneck") — NOT industry role
   - reason: Why this entity benefits — linked to specific variables from L1

2. overvalued_entities: Entities whose market value exceeds structural value.
   Each entity must have name, role, reason.

3. fragile_entities: Entities structurally fragile to regime shifts.
   Each entity must have name, role, reason.

## Hard Rule
- Role must reference variable types (SV/FV/CV/LV), not industry-specific roles.
- Reason must link to specific variables from L1, not vague descriptions.
- De-entity: entities are mapped to variable roles, not the other way around.

Use the provided real-world data to identify actual investment targets.
{peer_section}
Output must be valid JSON matching the L7PortfolioMapping schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def _build_drivers_summary(drivers: DriverSet) -> str:
    lines = []
    for d in drivers.drivers:
        lines.append(f"  - {d.name} ({d.type}, {d.direction}, dependency={d.system_dependency})")
    return "\n".join(lines) if lines else "None identified"


def _build_peer_section(peer_set: list[str]) -> str:
    if not peer_set:
        return ""
    return "Key entities to analyze: " + ", ".join(peer_set)


def run_l7(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l3_result: DriverSet,
    l4_result: RegimeState,
    l5_result: DistortionAnalysis,
    l6_result: AlphaSignal,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L7PortfolioMapping:
    """Execute L7 portfolio mapping."""
    prompt = L7_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        state_vars=_format_list(l1_result.state_variables),
        flow_vars=_format_list(l1_result.flow_variables),
        control_vars=_format_list(l1_result.control_variables),
        latent_vars=_format_list(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l3_result),
        current_regime=l4_result.current_regime,
        regime_confidence=l4_result.regime_confidence,
        market_belief=l5_result.market_belief,
        true_drivers=_format_list(l5_result.true_drivers),
        distortion_score=l5_result.distortion_score,
        alpha_signal=l6_result.alpha_signal,
        alpha_confidence=l6_result.confidence,
        peer_section=_build_peer_section(scan_input.peer_set),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, L7PortfolioMapping, context_data=context_data, temperature=temperature)
