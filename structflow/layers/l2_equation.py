"""L2: System Equation — Meta Dynamics Engine.

System Change = α * Flow Variables + β * Control Variables + γ * Latent Variables
Hard constraint: α + β + γ = 1.0

The system's change is decomposed into contributions from three variable types.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import MetaSystemDefinition, ScanInput, SystemEquation, VariableMapping

L2_PROMPT_TEMPLATE = """
Determine the system dynamics equation for this system.

System: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}
- Endogenous Feedback Loops: {feedback_loops}

L1 Variable Mapping:
- State Variables (SV): {state_vars}
- Flow Variables (FV): {flow_vars}
- Control Variables (CV): {control_vars}
- Latent Variables (LV): {latent_vars}

The system's change can be decomposed as:
  ΔState = α * Flow Variables + β * Control Variables + γ * Latent Variables

Where:
- α (flow_weight): How much of the system's change is driven by FLOW variables (cash flow, information flow, goods flow, risk transfer)?
- β (control_weight): How much is driven by CONTROL variables (interest rate, pricing, regulation, standards)?
- γ (latent_weight): How much is driven by LATENT variables (expectations, confidence, narrative, risk appetite)?

You MUST output a JSON object with exactly these fields:
- flow_weight: α (0-1) — weight of flow variables
- control_weight: β (0-1) — weight of control variables
- latent_weight: γ (0-1) — weight of latent variables

## Hard Rule
α + β + γ MUST equal 1.0 (100%).

Think carefully: in this specific system, which type of variable drives the most change?
- A financial market might be heavily latent-driven (expectations, confidence).
- A supply chain might be heavily flow-driven (goods flow, cash flow).
- A regulated industry might be heavily control-driven (regulation, pricing rules).

Use the provided real-world data to assess the actual dynamics.
Output must be valid JSON matching the SystemEquation schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def run_l2(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> SystemEquation:
    """Execute L2 system equation analysis."""
    prompt = L2_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        feedback_loops=_format_list(l0_result.endogenous_feedback_loops),
        state_vars=_format_list(l1_result.state_variables),
        flow_vars=_format_list(l1_result.flow_variables),
        control_vars=_format_list(l1_result.control_variables),
        latent_vars=_format_list(l1_result.latent_variables),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, SystemEquation, context_data=context_data, temperature=temperature)
