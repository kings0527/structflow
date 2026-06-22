"""L0: Meta System Definition — defines the system as a parameterizable dynamic system.

V2.1 Core Principle:
  Meta Layer = compress all industries into "State Variables + Flow Variables
  + Control Variables + Latent Variables" unified dynamic system expression.

The system is NOT described by industry semantics, but by its functional structure.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import MetaSystemDefinition, ScanInput

L0_PROMPT_TEMPLATE = """
Analyze the following system and define its meta-system structure.

System (Industry): {industry}
Region: {region}
Time Horizon: {time_horizon}

You are a Meta-Generalization Engine. Your job is NOT to describe the industry,
but to compress it into a parameterizable dynamic system.

You MUST output a JSON object with exactly these fields:

- system_type: What type of system is this? (e.g., "financial market", "supply chain", "platform economy", "resource extraction", "manufacturing ecosystem")
- core_function: The irreducible function this system performs — what would break if this system disappeared?
- state_variables: List of state variables (SV) — the system's current stock/存量 structure.
  Examples: capital stock, production capacity, user base, reserves, leverage level, inventory.
  These are ACCUMULATED quantities that change slowly.
- control_variables: List of control variables (CV) — leverage points that determine system behavior.
  Examples: interest rate, pricing power, entry rules, subsidies/taxes, standards, regulatory thresholds.
  These are variables that can be DIRECTLY manipulated.
- exogenous_drivers: List of external forces that impact the system from outside.
  Examples: geopolitical events, technological breakthroughs, demographic shifts, macro cycles.
- endogenous_feedback_loops: List of internal feedback mechanisms within the system.
  Examples: "higher prices → more investment → oversupply → price crash", "network effects → more users → more data → better product → more users".

## Hard Rule
You MUST be able to answer: "If this system disappeared tomorrow, who would suffer the most?"
Embed this answer implicitly in your core_function.

## Constraints
1. De-entity: Do NOT list specific companies. Describe variables and roles, not entities.
2. De-narrative: Do NOT use narrative/storytelling. Be structural and precise.
3. De-static: Must include dynamic elements (feedback loops, change drivers).

Use the provided real-world data to ground your analysis in current conditions.
Output must be valid JSON matching the MetaSystemDefinition schema.
"""


def run_l0(
    client: LLMClient,
    scan_input: ScanInput,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> MetaSystemDefinition:
    """Execute L0 meta system definition."""
    prompt = L0_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, MetaSystemDefinition, context_data=context_data, temperature=temperature)
