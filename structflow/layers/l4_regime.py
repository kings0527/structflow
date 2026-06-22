"""L4: Regime State — Meta Regime Layer.

Identifies the current system regime:
  expansion | contraction | transition | bubble | collapse
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DriverSet,
    MetaSystemDefinition,
    RegimeState,
    ScanInput,
    SystemEquation,
    VariableMapping,
)

L4_PROMPT_TEMPLATE = """
Identify the current regime of this system.

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

L2 System Equation:
- Flow Weight (α): {flow_weight}, Control Weight (β): {control_weight}, Latent Weight (γ): {latent_weight}

L3 Drivers:
{drivers_summary}

You MUST identify the current regime of this system. The system must be in exactly
one of these regimes:

- expansion: System is growing, variables are positive, feedback loops are reinforcing growth
- contraction: System is shrinking, variables are negative, feedback loops are reinforcing decline
- transition: System is shifting from one regime to another, variables are mixed
- bubble: System is in an unsustainable expansion, latent variables (confidence, risk appetite) are extreme
- collapse: System is in rapid deterioration, feedback loops are breaking down

You MUST output a JSON object with exactly these fields:
- current_regime: One of "expansion", "contraction", "transition", "bubble", "collapse"
- regime_confidence: How confident are you in this identification? (0-1)
- regime_drivers: List of key variables driving the current regime (from SV/FV/CV/LV)

## Hard Rule
The regime must be grounded in the variable analysis, not in narrative or opinion.
Each regime_driver must trace back to a specific variable from L1.

Use the provided real-world data to assess the actual current state.
Output must be valid JSON matching the RegimeState schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def _build_drivers_summary(drivers: DriverSet) -> str:
    lines = []
    for d in drivers.drivers:
        lines.append(f"  - {d.name} (type={d.type}, direction={d.direction}, elasticity={d.elasticity}, lag={d.lag}, volatility={d.volatility}, dependency={d.system_dependency})")
    return "\n".join(lines) if lines else "None identified"


def run_l4(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: SystemEquation,
    l3_result: DriverSet,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> RegimeState:
    """Execute L4 regime state identification."""
    prompt = L4_PROMPT_TEMPLATE.format(
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
        flow_weight=l2_result.flow_weight,
        control_weight=l2_result.control_weight,
        latent_weight=l2_result.latent_weight,
        drivers_summary=_build_drivers_summary(l3_result),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, RegimeState, context_data=context_data, temperature=temperature)
