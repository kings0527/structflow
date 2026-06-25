"""L6: Alpha Engine — mispricing extraction under bounded uncertainty.

V2.2: Enhanced with direction (long|short|neutral).
Alpha = Σ(Driver × Weight × Regime Multiplier × Mispricing Factor)

Constraints:
- Alpha cannot override driver structure
- Alpha must reference regime state
- Alpha must include scenario uncertainty
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    DriverSpace,
    MetaSystemDefinition,
    RegimeEngine,
    ScanInput,
    VariableMapping,
)

L6_PROMPT_TEMPLATE = """
Generate the alpha signal for this system.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}

L1 Variables:
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

L2 Drivers:
{drivers_summary}

L4 Regime: {current_regime} (confidence: {regime_confidence})
- Next: {next_regime} (prob: {transition_prob})

L5 Distortion:
- Market Belief: {market_belief}
- Structural Truth: {structural_truth}
- Mispricing Sources: {mispricing_sources}
- Distortion Score: {distortion_score}

Alpha = Σ(Driver × Weight × Regime Multiplier × Mispricing Factor)

Output:
1. consensus_view: What the market consensus believes
2. structural_view: What the structural analysis reveals
3. mispricing: The specific gap between consensus and structure
4. alpha_signal: Actionable signal — how to profit
5. direction: long | short | neutral
6. confidence: 0-1

## Hard Rules
1. Alpha CANNOT override driver structure — it must be consistent with L2 drivers.
2. Alpha MUST reference regime state — consider current regime and transition probability.
3. Alpha MUST include scenario uncertainty — acknowledge what could go wrong.
4. No Alpha Override: If drivers say negative, alpha cannot be positive without justification.
5. PRICE GROUNDING: If the Real-World Data Context contains current price information,
   your alpha_signal MUST reference the actual current price. Do NOT invent price levels.
   If current price is $1600, do not say 'break below $1800 support' — use actual levels.
6. TEMPORAL CLARITY: Clearly distinguish between past events (已发生),
   current conditions (当前), and future catalysts (计划中/未来).
7. EVIDENCE REVISION: The Real-World Data Context may contain contradiction evidence
   that challenges earlier analysis layers (L2 drivers, L3 feedback loops).
   If you find evidence in the context that CONTRADICTS an earlier claim:
   - ACKNOWLEDGE the contradiction in your structural_view
   - ADJUST your confidence downward if the contradiction is significant
   - Do NOT blindly trust earlier layers if search evidence contradicts them
   Example: If L3 claims 'deflationary loop' but context shows 'post-Dencun inflationary',
   your structural_view must note this contradiction.

Output must be valid JSON matching the AlphaEngine schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = [f"  - {d.name} ({d.maps_to_variable}, {d.direction}, elasticity={d.elasticity}, regime_dep={d.regime_dependency})" for d in drivers.drivers]
    return "\n".join(lines) if lines else "None"


def run_l6(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    l4_result: RegimeEngine,
    l5_result: DistortionEngine,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> AlphaEngine:
    prompt = L6_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
        current_regime=l4_result.current_regime,
        regime_confidence=l4_result.confidence,
        next_regime=l4_result.transition_probability.next_regime,
        transition_prob=l4_result.transition_probability.probability,
        market_belief=l5_result.market_belief,
        structural_truth=l5_result.structural_truth,
        mispricing_sources=_fmt(l5_result.mispricing_sources),
        distortion_score=l5_result.distortion_score,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, AlphaEngine, context_data=context_data, temperature=temperature)
