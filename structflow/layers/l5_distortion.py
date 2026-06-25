"""L5: Distortion Engine — detects gap between market belief and structural reality.

V2.2: structural_truth (str) replaces true_drivers (list[str]).
Mispricing types: cycle | structural | liquidity | narrative | policy
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    DistortionEngine,
    DriverSpace,
    MetaSystemDefinition,
    RegimeEngine,
    ScanInput,
    VariableMapping,
)

L5_PROMPT_TEMPLATE = """
Detect the distortion between market belief and structural reality.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}

L1 Variables:
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

L2 Drivers:
{drivers_summary}

L4 Regime: {current_regime} (confidence: {regime_confidence})
- Next likely: {next_regime} (prob: {transition_prob})

Detect where the market is WRONG about this system.

Output:
1. market_belief: What does the market currently believe?
2. structural_truth: What does the structural analysis actually reveal? (single string, not a list)
3. mispricing_sources: Specific gaps — where market belief diverges from reality
4. distortion_score: 0-1 (0=market correct, 1=massively distorted)

Mispricing types to consider: cycle | structural | liquidity | narrative | policy

## Hard Rules
1. Every L5 statement MUST trace back to at least 1 L2 driver + 1 L1 variable.
   If not traceable → CrossLayerConsistency FAILURE.
2. TEMPORAL CLARITY: When describing events or upgrades, clearly state whether they are:
   - 已发生 (past/completed, e.g., 'Dencun升级已于2024年3月完成')
   - 当前进行中 (current/ongoing)
   - 计划中/未来 (planned/future, e.g., 'Glamsterdam升级计划于2026年启动')
   Do NOT use present tense for future events. '将提升' not '大幅提升' for planned upgrades.
3. PRICE GROUNDING: If the Real-World Data Context contains current price data,
   reference actual price levels in your analysis. Do NOT invent price targets.

Output must be valid JSON matching the DistortionEngine schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = [f"  - {d.name} ({d.maps_to_variable}, {d.direction})" for d in drivers.drivers]
    return "\n".join(lines) if lines else "None"


def run_l5(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    l4_result: RegimeEngine,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> DistortionEngine:
    prompt = L5_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
        current_regime=l4_result.current_regime,
        regime_confidence=l4_result.confidence,
        next_regime=l4_result.transition_probability.next_regime,
        transition_prob=l4_result.transition_probability.probability,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, DistortionEngine, context_data=context_data, temperature=temperature)
