"""L7: Investment Mapping Layer (optional) — asset mapping with exposure metrics.

V2.2: Enhanced AssetMapping with exposure, sensitivity_to_drivers, risk_profile.
Roles: SV_controller | FV_bottleneck | CV_beneficiary | LV_reflection
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    DriverSpace,
    InvestmentMapping,
    MetaSystemDefinition,
    RegimeEngine,
    ScanInput,
    VariableMapping,
)

L7_PROMPT_TEMPLATE = """
Map investment targets based on the variable and driver analysis.

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

L4 Regime: {current_regime} (next: {next_regime}, prob: {transition_prob})

L5 Distortion: {market_belief} vs {structural_truth} (score: {distortion_score})

L6 Alpha: {alpha_signal} (direction: {alpha_direction}, confidence: {alpha_confidence})
{peer_section}

Map specific assets to investment categories. For each asset:
- asset: Entity name (company, commodity, instrument)
- role: Variable role — SV_controller | FV_bottleneck | CV_beneficiary | LV_reflection
- exposure: 0-1, how exposed to the identified alpha (0=low exposure, 1=high exposure)
- sensitivity_to_drivers: List of L2 driver names this asset is most sensitive to
- risk_profile: What is the SPECIFIC downside risk for this asset? (e.g., "If Glamsterdam upgrade delays, L2 competitors gain share" — NOT a list of risk factors, but a specific scenario where this asset loses)
- evidence_ids: Exact src_* IDs that verify identity, exposure, and risk
- verification_status: verified | partial | unverified
- observed_price: Only when a dated price source exists
- price_as_of: Observation date for observed_price

IMPORTANT: risk_profile should be ONE concrete risk scenario, not a comma-separated list of risks.
Good: "ETH price drops below $1,800 if ETF outflows continue for 3+ months"
Bad: "做空机构攻击, 宏观流动性收紧, L2价值回流不及预期"

Categories:
1. best_positioned: Assets best positioned to profit from the alpha
2. overvalued: Assets whose market value exceeds structural value
3. fragile: Assets structurally fragile to regime shifts

## Hard Rules
- Role must reference variable types (SV/FV/CV/LV), not industry roles.
- sensitivity_to_drivers must reference actual driver names from L2.
- Entities are OUTPUTS, not drivers — do not let entity reasoning override driver structure.
- PRICE GROUNDING: Use price only from the Canonical Input Profile market_snapshot
  or dated asset evidence. Otherwise leave observed_price and price_as_of null.
- TEMPORAL CLARITY: Clearly distinguish past (已发生), current (当前), and future (计划中) events.
- risk_profile for best_positioned assets should describe WHAT COULD GO WRONG,
  not why the asset is good (that's implied by the category).
- An asset cannot be verified without at least one exact evidence ID.
- Do not provide buy/sell recommendations, target prices, or upside percentages.

For every mapping, classify asset_type and populate ticker, venue and is_tradable.
A business unit is not an investable asset. It may be described as fragile, but
must use asset_type=business_unit and is_tradable=false. Never mark a mapping as
verified unless its identity and tradability status are supported by evidence IDs.

Output must be valid JSON matching the InvestmentMapping schema.
"""


def _fmt(items: list[str]) -> str:
    return "; ".join(items) if items else "N/A"


def _build_drivers_summary(drivers: DriverSpace) -> str:
    lines = [f"  - {d.name} ({d.maps_to_variable}, {d.direction})" for d in drivers.drivers]
    return "\n".join(lines) if lines else "None"


def _build_peer_section(peer_set: list[str]) -> str:
    if not peer_set:
        return ""
    return "Key entities to analyze: " + ", ".join(peer_set)


def run_l7(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    l1_result: VariableMapping,
    l2_result: DriverSpace,
    l4_result: RegimeEngine,
    l5_result: DistortionEngine,
    l6_result: AlphaEngine,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> InvestmentMapping:
    prompt = L7_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        state_vars=_fmt(l1_result.state_variables),
        flow_vars=_fmt(l1_result.flow_variables),
        control_vars=_fmt(l1_result.control_variables),
        latent_vars=_fmt(l1_result.latent_variables),
        drivers_summary=_build_drivers_summary(l2_result),
        current_regime=l4_result.current_regime,
        next_regime=l4_result.transition_probability.next_regime,
        transition_prob=l4_result.transition_probability.probability,
        market_belief=l5_result.market_belief,
        structural_truth=l5_result.structural_truth,
        distortion_score=l5_result.distortion_score,
        alpha_signal=l6_result.alpha_signal,
        alpha_direction=l6_result.direction,
        alpha_confidence=l6_result.confidence,
        peer_section=_build_peer_section(scan_input.peer_set),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, InvestmentMapping, context_data=context_data, temperature=temperature)
