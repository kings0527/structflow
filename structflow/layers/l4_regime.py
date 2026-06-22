"""L4: Nonlinear Regime Engine — state classification with transition probability.

V2.2: Enhanced with transition_probability + shock regime.
Regime(t) = f(SV, FV, CV, LV, ΔDrivers)
Regime changes only if: Σ(Weighted Driver Shocks) > Threshold
Threshold = f(volatility, leverage, inventory level)
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DriverSpace,
    FlowFeedbackSystem,
    MetaSystemDefinition,
    NonlinearDynamics,
    RegimeEngine,
    ScanInput,
    VariableMapping,
)

L4_PROMPT_TEMPLATE = """
Identify the current regime and transition probability of this system.

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
{feedback_summary}

Nonlinear Dynamics:
- Inventory Cycle: stage={cycle_stage}, pressure={inventory_pressure}, price_sensitivity={price_sensitivity}
- Capacity Lag: {capex_lag} ({supply_delay})
- Demand Elasticity: {demand_elasticity} (state_dependency={state_dep})

Identify the current regime. The system must be in exactly one of:
- expansion: System growing, variables positive, feedback reinforcing growth
- contraction: System shrinking, variables negative, feedback reinforcing decline
- transition: System shifting between regimes, variables mixed
- bubble: Unsustainable expansion, latent variables (confidence, risk appetite) extreme
- collapse: Rapid deterioration, feedback loops breaking down
- shock: Sudden exogenous disruption, system in stress response

Also identify the most likely NEXT regime and its transition probability.
Regime changes only if: Σ(Weighted Driver Shocks) > Threshold
Threshold = f(volatility, leverage, inventory level)

Output:
- current_regime: expansion | contraction | transition | bubble | collapse | shock
- confidence: 0-1
- transition_probability: {{ next_regime: string, probability: 0-1 }}

Output must be valid JSON matching the RegimeEngine schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = [f"  - {d.name} ({d.direction}, elasticity={d.elasticity}, regime_dep={d.regime_dependency})" for d in drivers.drivers]
    return "\n".join(lines) if lines else "None"


def _build_feedback_summary(ff: FlowFeedbackSystem) -> str:
    lines = [f"  - {l.loop_name} ({l.type}, amp={l.amplification_factor}): {l.mechanism}" for l in ff.feedback_loops]
    return "\n".join(lines) if lines else "None"


def run_l4(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    l3_result: FlowFeedbackSystem,
    nl_result: NonlinearDynamics,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> RegimeEngine:
    prompt = L4_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        failure_mode=l0_result.failure_mode,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
        feedback_summary=_build_feedback_summary(l3_result),
        cycle_stage=nl_result.inventory_cycle.cycle_stage,
        inventory_pressure=nl_result.inventory_cycle.inventory_pressure,
        price_sensitivity=nl_result.inventory_cycle.price_sensitivity,
        capex_lag=nl_result.capacity_lag.capex_cycle_lag,
        supply_delay=nl_result.capacity_lag.supply_response_delay,
        demand_elasticity=nl_result.demand_elasticity.elasticity,
        state_dep=nl_result.demand_elasticity.state_dependency,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, RegimeEngine, context_data=context_data, temperature=temperature)
