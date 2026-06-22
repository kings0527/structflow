"""L0: Meta Layer — defines the industry ontology."""

from __future__ import annotations

from typing import Optional

from structflow.llm_client import LLMClient
from structflow.models import L0IndustryDefinition, ScanInput

L0_PROMPT_TEMPLATE = """
Analyze the following industry and define its meta ontology.

Industry: {industry}
Region: {region}
Time Horizon: {time_horizon}

You MUST output a JSON object with exactly these fields:
- core_need: What rigid demand does this industry fulfill? (string — one sentence identifying the irreducible need)
- substitution_risk: How easily can this be substituted? (float 0-1, 0=no substitution possible, 1=easily substituted)
- demand_elasticity: How sensitive is demand to price changes? (float 0-1, 0=perfectly inelastic/rigid demand, 1=perfectly elastic/discretionary)
- narrative_dependency: How dependent is this industry on policy or narrative? (float 0-1, 0=independent, 1=fully dependent)
- regulatory_dependency: How dependent is this industry on specific regulations or regulatory frameworks? (float 0-1, 0=no regulatory dependency, 1=fully regulated)

## Hard Rule
You MUST be able to answer: If this industry disappeared tomorrow, who would suffer the most?
Embed this answer implicitly in your core_need — it should identify WHO depends on this industry and WHY.

Rules:
- Be precise and structural. No storytelling.
- core_need must be a single sentence identifying the irreducible need and who depends on it.
- All scores must be justified by structural facts, not opinions.
- Use the provided real-world data to ground your analysis in current market conditions.
"""


def run_l0(
    client: LLMClient,
    scan_input: ScanInput,
    context_data: Optional[str] = None,
    retry_feedback: Optional[str] = None,
    temperature: Optional[float] = None,
) -> L0IndustryDefinition:
    """Execute L0 industry meta definition analysis."""
    prompt = L0_PROMPT_TEMPLATE.format(
        industry=scan_input.industry,
        region=scan_input.region or "global",
        time_horizon=scan_input.time_horizon.value,
    )
    if retry_feedback:
        prompt += f"\n\n## 上次输出的问题（请修正）\n{retry_feedback}"
    return client.structured_call(prompt, L0IndustryDefinition, context_data=context_data, temperature=temperature)
