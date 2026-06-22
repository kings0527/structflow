"""Nonlinear Dynamics — inventory cycle, capacity lag, demand elasticity.

V2.2 NEW: Feeds into L4 Regime Engine.
Price ≠ linear function of cost.
Price = f(inventory, leverage, sentiment, marginal_cost, liquidity)
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DriverSpace,
    FlowFeedbackSystem,
    MetaSystemDefinition,
    NonlinearDynamics,
    ScanInput,
    VariableMapping,
)

NONLINEAR_PROMPT_TEMPLATE = """
Assess the nonlinear dynamics of this system.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}
- Failure Mode: {failure_mode}

L1 Variables:
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

L2 Drivers:
{drivers_summary}

L3 Flow + Feedback:
- Flow types: {flow_types}
- Feedback loops: {feedback_loops}

Assess three nonlinear modules:

1. Inventory Cycle:
   - cycle_stage: early | mid | late | crash
   - inventory_pressure: 0-1 (0=low/no pressure, 1=extreme overhang)
   - price_sensitivity: 0-1 (how sensitive price is to inventory changes)

2. Capacity Lag:
   - capex_cycle_lag: Time from investment decision to capacity coming online (in months, e.g., "18 months")
   - supply_response_delay: short | mid | long

3. Demand Elasticity:
   - elasticity: 0-1 (0=inelastic/rigid demand, 1=highly elastic)
   - state_dependency: true if demand depends on system state, false if independent

## Hard Rule
All pricing is NONLINEAR unless explicitly proven stable.
Do NOT assume linear relationships between cost and price.

Output must be valid JSON matching the NonlinearDynamics schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = [f"  - {d.name} ({d.category}, {d.direction}, elasticity={d.elasticity})" for d in drivers.drivers]
    return "\n".join(lines) if lines else "None"


def _build_feedback_summary(ff: FlowFeedbackSystem) -> str:
    lines = [f"  - {l.loop_name} ({l.type}, amp={l.amplification_factor})" for l in ff.feedback_loops]
    return "\n".join(lines) if lines else "None"


def run_nonlinear(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    l3_result: FlowFeedbackSystem,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> NonlinearDynamics:
    prompt = NONLINEAR_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        failure_mode=l0_result.failure_mode,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
        flow_types=_fmt(l3_result.flow_types),
        feedback_loops=_build_feedback_summary(l3_result),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, NonlinearDynamics, context_data=context_data, temperature=temperature)
