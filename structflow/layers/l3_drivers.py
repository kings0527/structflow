"""L3: Driver Set — Driver Abstraction Layer.

Replaces V2's industry-specific driver layer with a unified driver format.
All drivers must come from changes in SV/FV/CV/LV.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DriverSet,
    MetaSystemDefinition,
    ScanInput,
    SystemEquation,
    VariableMapping,
)

L3_PROMPT_TEMPLATE = """
Identify the key driver factors for this system.

System: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}

L1 Variable Mapping:
- State Variables (SV): {state_vars}
- Flow Variables (FV): {flow_vars}
- Control Variables (CV): {control_vars}
- Latent Variables (LV): {latent_vars}

L2 System Equation:
- Flow Weight (α): {flow_weight}
- Control Weight (β): {control_weight}
- Latent Weight (γ): {latent_weight}

You MUST identify the key driver factors — variables that will determine this system's
future trajectory. These are NOT descriptions of the current state, but the FACTORS
that will drive change.

For each driver, output:
- name: Driver name (e.g., "Real Interest Rate", "Central Bank Buying", "AI Workload Growth")
- type: Driver type — one of: "macro", "micro", "policy", "behavioral", "financial"
- direction: "+" (positive for system) or "-" (negative for system)
- elasticity: How sensitive is the system to this driver? (0=inelastic, 1=highly elastic)
- lag: Time lag for impact — "short", "mid", or "long"
- volatility: How volatile/unpredictable is this driver? (0=stable, 1=highly volatile)
- system_dependency: How dependent is the system on this driver? (0=peripheral, 1=critical)

## Hard Rule
ALL drivers MUST come from changes in SV/FV/CV/LV. Every driver must be traceable
to a change in one of the four variable types. Do NOT invent drivers that are
unconnected to the variable mapping.

## De-narrative Rule
Narrative can ONLY be a latent variable (LV), not a driver itself.
If "market narrative" is a driver, it must be framed as "shift in LV: market narrative"
not as a standalone driver.

Use the provided real-world data to identify actual market drivers.
Output must be valid JSON matching the DriverSet schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def run_l3(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: SystemEquation,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> DriverSet:
    """Execute L3 driver set analysis."""
    prompt = L3_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        state_vars=_format_list(l1_result.state_variables),
        flow_vars=_format_list(l1_result.flow_variables),
        control_vars=_format_list(l1_result.control_variables),
        latent_vars=_format_list(l1_result.latent_variables),
        flow_weight=l2_result.flow_weight,
        control_weight=l2_result.control_weight,
        latent_weight=l2_result.latent_weight,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, DriverSet, context_data=context_data, temperature=temperature)
