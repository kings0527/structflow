"""L0: Industry Definition Layer — defines the industry ontology."""

from __future__ import annotations

from structflow.llm_client import LLMClient
from structflow.models import L0IndustryDefinition, ScanInput

L0_PROMPT_TEMPLATE = """
Analyze the following industry and define its ontology.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

You MUST output a JSON object with exactly these fields:
- core_need: What rigid demand does this industry fulfill? (string)
- substitution_risk: How easily can this be substituted? (float 0-1, 0=no substitution, 1=easily substituted)
- demand_stability: How stable is demand? (float 0-1, 0=volatile, 1=stable)
- narrative_dependency: How dependent is this industry on policy or narrative? (float 0-1, 0=independent, 1=fully dependent)

Rules:
- Be precise and structural. No storytelling.
- core_need must be a single sentence identifying the irreducible need.
- All scores must be justified by structural facts, not opinions.
"""


def run_l0(client: LLMClient, scan_input: ScanInput) -> L0IndustryDefinition:
    """Execute L0 industry definition analysis."""
    prompt = L0_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
    )
    return client.structured_call(prompt, L0IndustryDefinition)
