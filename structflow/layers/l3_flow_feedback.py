"""L3: Flow + Feedback System — identifies flow types and feedback loops.

V2.2 NEW: Replaces V2.1's SystemEquation.
Flow types: capital, goods, information, risk, subsidy.
Feedback loops: minimum 3, at least 1 reinforcing + 1 balancing.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import DriverSpace, FlowFeedbackSystem, MetaSystemDefinition, ScanInput, VariableMapping

L3_PROMPT_TEMPLATE = """
Identify the flow types and feedback loops in this system.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}

L1 Variable Space:
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

L2 Drivers:
{drivers_summary}

Identify:
1. Flow types present in this system (from: capital flow, goods flow, information flow, risk flow, subsidy flow)
2. Feedback loops (minimum 3, at least 1 reinforcing + 1 balancing)

For each feedback loop, output:
- loop_name: Name of the feedback loop
- type: "reinforcing" (amplifies change) or "balancing" (dampens change / restores equilibrium)
- mechanism: How the loop works — the causal chain (e.g., "higher prices → more investment → oversupply → price crash")
- trigger: What condition activates this loop
- amplification_factor: 0-1, how much the loop amplifies changes (0=damping, 1=extreme amplification)

## Hard Rules
1. Minimum 3 feedback loops.
2. At least 1 reinforcing loop (amplifies change).
3. At least 1 balancing loop (dampens change / restores equilibrium).
4. Each loop mechanism must be a clear causal chain, not a vague description.

Output must be valid JSON matching the FlowFeedbackSystem schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = []
    for d in drivers.drivers:
        lines.append(f"  - {d.name} (cat={d.category}, maps={d.maps_to_variable}, dir={d.direction}, elasticity={d.elasticity})")
    return "\n".join(lines) if lines else "None"


def run_l3(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> FlowFeedbackSystem:
    prompt = L3_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, FlowFeedbackSystem, context_data=context_data, temperature=temperature)
