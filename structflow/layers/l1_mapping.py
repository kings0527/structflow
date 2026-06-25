"""L1: Variable Space — maps system into SV / FV / CV / LV.

V2.2: Uses system template METHODOLOGY (not variable list) as guidance.
Template tells LLM HOW to think (structure, questions, patterns),
not WHAT to think (specific variables to copy).
LLM applies methodology to generate specific variables for the actual system.
"""

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
{methodology_section}
Output a JSON object with exactly these fields:

- state_variables (SV): Persistent stock variables — accumulated quantities that change slowly.
- flow_variables (FV): Rate-of-change variables — how the system changes over time.
- control_variables (CV): Policy/pricing/constraint variables — directly manipulable leverage points.
- latent_variables (LV): Unobservable state drivers — decisive but not directly measurable.

## Hard Rules
1. De-entity: NO company names. Describe variables, not entities.
2. De-narrative: Narrative can ONLY appear as LV, never in SV/FV/CV.
3. Each variable type must have at least 3 items.
4. Each variable must be a single clear phrase, specific to THIS system.
5. Do NOT copy template examples directly — apply the methodology to generate system-specific variables.

Output must be valid JSON matching the VariableMapping schema.
"""


def run_l1(
    client: LLMClient,
    scan_input: ScanInput,
    l0_result: MetaSystemDefinition,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
    template_methodology: Optional[dict[str, str]] = None,
) -> VariableMapping:
    """Execute L1 variable mapping.

    Args:
        template_methodology: If provided, contains structure description and
            per-variable-type methodology (questions to ask, patterns to look for).
            This guides the LLM's thinking process — NOT a variable list to copy.
    """
    # Build methodology section — tells LLM HOW to think, not WHAT to think
    if template_methodology:
        methodology_section = "\n## System Structure & Methodology\n\n"
        methodology_section += "This system has been identified with the following structural characteristics:\n\n"
        methodology_section += f"**Structure**: {template_methodology.get('structure', '')}\n\n"
        methodology_section += "**Methodology** — Use these questions to IDENTIFY variables (do NOT copy the examples):\n\n"

        for var_type in ["SV", "FV", "CV", "LV"]:
            guidance = template_methodology.get(var_type, "")
            if guidance:
                methodology_section += f"**{var_type}**: {guidance}\n\n"

        methodology_section += (
            "IMPORTANT: The above is METHODOLOGY, not a variable list. "
            "Apply these questions to THIS specific system and generate variables "
            "that are SPECIFIC to it. Do not copy the example patterns directly.\n\n"
        )
    else:
        methodology_section = ""

    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        system_boundary=l0_result.system_boundary,
        failure_mode=l0_result.failure_mode,
        methodology_section=methodology_section,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, VariableMapping, context_data=context_data, temperature=temperature)
"""L1: Variable Space — maps system into SV / FV / CV / LV.

V2.2: Uses system template as scaffolding when available.
Template provides default variables — LLM can modify/extend but starts from structured base.
This prevents variable drift across runs (same industry → same variable structure).
"""

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
{scaffolding}
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
    template_variables: Optional[dict[str, list[str]]] = None,
) -> VariableMapping:
    """Execute L1 variable mapping.

    Args:
        template_variables: If provided, these are used as scaffolding.
            The LLM starts from these defaults and can modify/extend them.
            This prevents variable drift across runs.
    """
    # Build scaffolding section from template
    if template_variables:
        scaffolding = "\n## Suggested Variables (from system template — modify as needed)\n"
        scaffolding += "Use these as STARTING POINT. You can modify, add, or remove variables,\n"
        scaffolding += "but the structure should remain similar.\n\n"
        for var_type, vars in template_variables.items():
            scaffolding += f"- {var_type}: {', '.join(vars)}\n"
        scaffolding += "\n"
    else:
        scaffolding = ""

    prompt = L1_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        system_type=l0_result.system_type,
        core_function=l0_result.core_function,
        system_boundary=l0_result.system_boundary,
        failure_mode=l0_result.failure_mode,
        scaffolding=scaffolding,
    )
    if retry_feedback:
        prompt += f"\n\n## Previous output issues (please fix):\n{retry_feedback}"
    return client.structured_call(prompt, VariableMapping, context_data=context_data, temperature=temperature)
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
