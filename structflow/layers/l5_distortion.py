"""L5: Distortion Analysis — Meta Distortion Layer.

Detects the gap between market cognition and system's true structure.
This is the core capability that was missing in V2.

Must answer:
  What does the market believe?
  What truly drives the system?
  Where is the gap?
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DistortionAnalysis,
    DriverSet,
    MetaSystemDefinition,
    RegimeState,
    ScanInput,
    SystemEquation,
    VariableMapping,
)

L5_PROMPT_TEMPLATE = """
Detect the distortion between market belief and structural reality.

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
- α={flow_weight}, β={control_weight}, γ={latent_weight}

L3 Drivers:
{drivers_summary}

L4 Regime:
- Current Regime: {current_regime} (confidence: {regime_confidence})
- Regime Drivers: {regime_drivers}

You are a Meta Distortion Detector. Your task is to find where the market is WRONG
about this system — where market belief diverges from structural reality.

You MUST output a JSON object with exactly these fields:

1. market_belief: What does the market currently believe about this system?
   This is the dominant consensus — what most participants think drives the system.
   Example: "Market believes gold rises because of safe-haven demand during crises"

2. true_drivers: What actually drives the system based on your structural analysis?
   List the REAL drivers from L1-L4 analysis.
   Example: ["Central bank buying (SV change)", "Real interest rate (CV)", "Dollar weakness (exogenous)"]

3. mispricing_sources: Where specifically is the market wrong?
   List specific gaps between market_belief and true_drivers.
   Example: ["Market underestimates central bank buying persistence", "Market overweights crisis hedging narrative"]

4. distortion_score: Overall distortion level (0-1).
   0 = market is perfectly correct, 1 = market is completely wrong.
   Be honest — if the market is mostly right, say so with a low score.

## Hard Rule
You MUST answer three questions:
- What is the market believing? → market_belief
- What is truly driving the system? → true_drivers
- Where is the gap? → mispricing_sources

Use the provided real-world data to identify actual market consensus vs structural reality.
Output must be valid JSON matching the DistortionAnalysis schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def _build_drivers_summary(drivers: DriverSet) -> str:
    lines = []
    for d in drivers.drivers:
        lines.append(f"  - {d.name} ({d.type}, {d.direction}, elasticity={d.elasticity}, dependency={d.system_dependency})")
    return "\n".join(lines) if lines else "None identified"


def run_l5(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: SystemEquation,
    l3_result: DriverSet,
    l4_result: RegimeState,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> DistortionAnalysis:
    """Execute L5 distortion analysis."""
    prompt = L5_PROMPT_TEMPLATE.format(
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
        drivers_summary=_build_drivers_summary(l3_result),
        current_regime=l4_result.current_regime,
        regime_confidence=l4_result.regime_confidence,
        regime_drivers=_format_list(l4_result.regime_drivers),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, DistortionAnalysis, context_data=context_data, temperature=temperature)
