"""L0: Meta System Definition — defines the system as a function, not an industry.

V2.2: Simplified — variables moved to L1, feedback moved to L3.
Focus: what the system IS, what BREAKS if it disappears.
"""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import MetaSystemDefinition, ScanInput

L0_PROMPT_TEMPLATE = """
Analyze the following system and define its meta-structure.

System (Industry): {industry}
Region: {region}
Time Horizon: {time_horizon}

You are a Meta-Generalization Engine. Your job is NOT to describe the industry,
but to define it as a dynamic constrained system.

You MUST output a JSON object with exactly these fields:

- system_type: What type of system is this? (e.g., "financial market", "supply chain", "platform economy")
- core_function: The irreducible function this system performs — what breaks if this system disappeared?
- system_boundary: What is INSIDE vs OUTSIDE the system? Where does the system end? What is explicitly excluded?
- failure_mode: How does this system break? What is the failure cascade? What happens when it collapses?

## Hard Rules
1. Define system as FUNCTION, not industry name.
2. Must describe what breaks if system disappears.
3. Must avoid entity-heavy descriptions.
4. system_boundary must be explicit — what is in-scope vs out-of-scope.
5. failure_mode must describe the cascade, not just "it crashes".

Use the provided real-world data to ground your analysis.
Output must be valid JSON matching the MetaSystemDefinition schema.
"""


def run_l0(
    client: LLMClient,
    scan_input: ScanInput,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> MetaSystemDefinition:
    prompt = L0_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, MetaSystemDefinition, context_data=context_data, temperature=temperature)
