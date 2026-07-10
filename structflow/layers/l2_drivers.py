"""L2: Driver Engine — Core Causal Layer with quantified drivers.

V2.2: Every driver MUST map to exactly one variable group (SV/FV/CV/LV).
Direction can be '+', '-', or 'nonlinear'.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import DriverSpace, MetaSystemDefinition, ScanInput, VariableMapping

L2_PROMPT_TEMPLATE = """
Identify the key causal drivers for this system.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}
- Failure Mode: {failure_mode}

L1 Variable Space:
- SV (State): {state_vars}
- FV (Flow): {flow_vars}
- CV (Control): {control_vars}
- LV (Latent): {latent_vars}

Identify the key causal driver factors — variables that determine the system's trajectory.
These are NOT descriptions of current state, but FACTORS that drive change.

For each driver, output:
- name: Driver name
- category: macro | micro | policy | behavioral | financial | structural
- maps_to_variable: Which variable group this driver affects — SV | FV | CV | LV
- direction: "+" (positive), "-" (negative), or "nonlinear" (non-monotonic/threshold-based)
- elasticity: 0-1, how sensitive the system is to this driver
- volatility: 0-1, how unpredictable this driver is
- lag: short | mid | long
- regime_dependency: 0-1, how dependent on current regime

Also output covered_segment_ids and covered_dimension_ids using the exact IDs
from the binding coverage contract. An ID is valid only when at least one driver
explicitly models that item.

## Hard Rules
1. Every driver MUST map to exactly one variable group (SV/FV/CV/LV).
2. No free-text drivers — all must be quantified.
3. No duplicate semantic drivers.
4. Narrative drivers must map to LV only.
5. Driver is valid only if: measurable proxy exists + directional impact defined + lag structure defined.
6. category values MUST be the exact lowercase English enum values listed above.
7. Coverage IDs are machine bindings. Copy them exactly; never translate or invent IDs.

Output must be valid JSON matching the DriverSpace schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def run_l2(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> DriverSpace:
    prompt = L2_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        failure_mode=l0_result.failure_mode,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, DriverSpace, context_data=context_data, temperature=temperature)
