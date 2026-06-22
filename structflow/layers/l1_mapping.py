"""L1: Variable Mapping — maps any system into SV/FV/CV/LV.

Meta Mapping Function: System → {SV, FV, CV, LV}

All industries must be mapped to four types of base variables:
(1) State Variables (SV) — system's current stock structure
(2) Flow Variables (FV) — system's change paths
(3) Control Variables (CV) — leverage points
(4) Latent Variables (LV) — unobservable but decisive
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import MetaSystemDefinition, ScanInput, VariableMapping

L1_PROMPT_TEMPLATE = """
Map the following system into four types of base variables.

System: {industry}
Region: {region}
Time Horizon: {time_horizon}

L0 Meta System Definition:
- System Type: {system_type}
- Core Function: {core_function}
- State Variables (from L0): {l0_state_vars}
- Control Variables (from L0): {l0_control_vars}
- Exogenous Drivers: {exogenous_drivers}
- Endogenous Feedback Loops: {feedback_loops}

You MUST output a JSON object with exactly these fields:

1. state_variables (SV): The system's current "stock structure" — accumulated quantities.
   Examples: capital stock, production capacity, user base, reserves, leverage level, inventory.
   These are STOCK variables that change slowly and determine the system's baseline.

2. flow_variables (FV): The system's change paths — rates of change.
   Examples: cash flow, information flow, goods flow, risk transfer flow, capital flow.
   These are FLOW variables that describe how the system changes.

3. control_variables (CV): Leverage points that determine system behavior.
   Examples: interest rate, pricing power, entry rules, subsidies/taxes, standards, regulatory thresholds.
   These are variables that can be DIRECTLY manipulated to change the system.

4. latent_variables (LV): Unobservable variables that determine system results.
   Examples: expectations, confidence, narrative, risk appetite, liquidity mismatch, trust.
   These cannot be directly measured but are DECISIVE for outcomes.

## Hard Rules
1. De-entity: Do NOT list specific companies. Describe variables, not entities.
2. De-narrative: Narrative can ONLY appear as a latent variable (LV), never as a driver or state variable.
3. Each variable must be a single, clear phrase (not a paragraph).
4. Each variable type must have at least 3 items.

Use the provided real-world data to ground your variable mapping.
Output must be valid JSON matching the VariableMapping schema.
"""


def _format_list(items: list[str]) -> str:
    if not items:
        return "N/A"
    return "; ".join(items)


def run_l1(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> VariableMapping:
    """Execute L1 variable mapping."""
    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        l0_state_vars=_format_list(l0_result.state_variables),
        l0_control_vars=_format_list(l0_result.control_variables),
        exogenous_drivers=_format_list(l0_result.exogenous_drivers),
        feedback_loops=_format_list(l0_result.endogenous_feedback_loops),
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, VariableMapping, context_data=context_data, temperature=temperature)
