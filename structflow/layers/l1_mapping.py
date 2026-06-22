"""L1: Variable Space — maps system into SV / FV / CV / LV."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import MetaSystemDefinition, ScanInput, VariableMapping

L1_PROMPT_TEMPLATE = """
Map the following system into four types of base variables.

System: {industry}
Region: {region}

L0 Meta:
- System Type: {system_type}
- Core Function: {core_function}
- System Boundary: {system_boundary}
- Failure Mode: {failure_mode}

Output a JSON object with exactly these fields:

- state_variables (SV): Persistent stock variables — accumulated quantities.
  Examples: capacity, inventory, capital stock, installed base, market share.
- flow_variables (FV): Rate-of-change variables — how the system changes.
  Examples: production volume, cash flow, shipment, investment flow, trade flow.
- control_variables (CV): Policy/pricing/constraint variables — directly manipulable.
  Examples: interest rate, carbon tax, tariffs, regulation intensity, subsidy level, quota allocation.
- latent_variables (LV): Unobservable state drivers — decisive but not directly measurable.
  Examples: expectation, sentiment, narrative, risk appetite, uncertainty.

## Hard Rules
1. De-entity: NO company names. Describe variables, not entities.
2. De-narrative: Narrative can ONLY appear as LV, never in SV/FV/CV.
3. Each variable type must have at least 3 items.
4. Each variable must be a single clear phrase.

Output must be valid JSON matching the VariableMapping schema.
"""


def run_l1(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> VariableMapping:
    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        system_boundary=l0_result.system_boundary,
        failure_mode=l0_result.failure_mode,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, VariableMapping, context_data=context_data, temperature=temperature)
