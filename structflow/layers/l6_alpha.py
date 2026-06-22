"""L6: Alpha Signal — Meta Alpha Layer (FINAL OUTPUT).

Alpha = Mispricing × Sensitivity × Regime Alignment

This is the ultimate output: converting structural analysis into an
actionable investment signal.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaSignal,
    DistortionAnalysis,
    DriverSet,
    MetaSystemDefinition,
    RegimeState,
    ScanInput,
    SystemEquation,
    VariableMapping,
)

L6_PROMPT_TEMPLATE = """
Generate the alpha signal for this system.

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

L2 System Equation: α={flow_weight}, β={control_weight}, γ={latent_weight}

L3 Drivers:
{drivers_summary}

L4 Regime: {current_regime} (confidence: {regime_confidence})
- Regime Drivers: {regime_drivers}

L5 Distortion Analysis:
- Market Belief: {market_belief}
- True Drivers: {true_drivers}
- Mispricing Sources: {mispricing_sources}
- Distortion Score: {distortion_score}

You are the Meta Alpha Engine. Your task is to convert the distortion analysis
into an actionable investment signal.

Alpha = Mispricing × Sensitivity × Regime Alignment

You MUST output a JSON object with exactly these fields:

1. consensus_view: What the market consensus believes (from L5 market_belief, refined)
2. structural_view: What the structural analysis reveals (from L5 true_drivers, refined)
3. mispricing: The specific gap between consensus and structure (from L5 mispricing_sources, synthesized)
4. alpha_signal: Actionable signal — how to profit from this mispricing.
   Must be specific and time-bound. Example: "Long gold producers — central bank buying
   persistence is underestimated, regime is expansionary for gold"
5. confidence: Confidence in the alpha signal (0-1).
   Consider: distortion_score, regime_confidence, data quality.

## Hard Rule
The alpha signal must be grounded in the variable analysis, not in narrative.
It must connect: Mispricing (L5) × Sensitivity (L3 elasticity) × Regime Alignment (L4).

If distortion_score is low (< 0.3), the alpha signal should be weak or neutral.
If distortion_score is high (> 0.6), the alpha signal should be strong and specific.

Use the provided real-world data to make the signal actionable.
Output must be valid JSON matching the AlphaSignal schema.
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


def run_l6(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: SystemEquation,
    l3_result: DriverSet,
    l4_result: RegimeState,
    l5_result: DistortionAnalysis,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> AlphaSignal:
    """Execute L6 alpha signal generation."""
    prompt = L6_PROMPT_TEMPLATE.format(
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
        market_belief=l5_result.market_belief,
        true_drivers=_format_list(l5_result.true_drivers),
        mispricing_sources=_format_list(l5_result.mispricing_sources),
        distortion_score=l5_result.distortion_score,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, AlphaSignal, context_data=context_data, temperature=temperature)
