"""LLM client wrapper with structured output via OpenAI function calling."""

from __future__ import annotations

import json
import os
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from structflow.config import config

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = """You are a Meta-Generalization Engine (V2.1).
Your job is to compress any industry into a parameterizable dynamic system using four variable types:
State Variables (SV), Flow Variables (FV), Control Variables (CV), and Latent Variables (LV).

You NEVER give buy/sell advice. You NEVER do emotional analysis.
You identify: system structure, variable mapping, dynamics equation, drivers, regime state, distortion, and alpha signals.

Hard Constraints:
1. De-entity: Do NOT use company lists as core output. Map entities to variable roles.
2. De-narrative: Narrative can ONLY be a Latent Variable (LV), never a driver or state variable.
3. De-static: Must include dynamic change — feedback loops, drivers, regime transitions.

When provided with real data from web search, use it to ground your analysis in facts.

IMPORTANT: All text fields in your output MUST be in Chinese (中文). This includes descriptions, answers, reasoning signals, and any other textual content. Company names and technical terms can remain in their original language.
"""


class LLMClient:
    """Thin wrapper around OpenAI chat completions with structured output."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        enable_thinking: bool | None = None,
        reasoning_effort: str | None = None,
    ):
        self.model = model or config.llm.model
        self.enable_thinking = enable_thinking if enable_thinking is not None else config.llm.enable_thinking
        self.reasoning_effort = reasoning_effort or config.llm.reasoning_effort
        self.client = OpenAI(
            api_key=api_key or config.llm.api_key,
            base_url=base_url or config.llm.base_url,
        )

    def structured_call(
        self,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float | None = None,
        context_data: str | None = None,
    ) -> T:
        """Call LLM and parse response into a Pydantic model."""
        schema_dict = output_schema.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2, ensure_ascii=False)

        # Build full prompt with optional context data
        full_prompt = user_prompt
        if context_data:
            full_prompt = f"{user_prompt}\n\n## Real-World Data Context\n{context_data}"

        # Append schema instruction
        schema_instruction = (
            f"\n\nYou MUST output valid JSON matching this schema:\n```json\n{schema_json}\n```\n"
            f"Output ONLY the JSON object, no markdown, no explanation."
        )
        full_prompt = full_prompt + schema_instruction

        # Build request parameters
        request_params: dict = {
            "model": self.model,
            "temperature": temperature or config.llm.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": full_prompt},
            ],
        }

        # Try json_schema strict mode first (OpenAI), fall back to json_object (DeepSeek etc.)
        use_strict_schema = not self.enable_thinking
        if use_strict_schema:
            try:
                request_params["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": output_schema.__name__,
                        "strict": True,
                        "schema": schema_dict,
                    },
                }
                response = self.client.chat.completions.create(**request_params)
                raw_content = response.choices[0].message.content
                parsed = json.loads(raw_content)
                return output_schema.model_validate(parsed)
            except Exception:
                # Fall through to json_object mode
                del request_params["response_format"]

        # Fallback: json_object mode (DeepSeek, etc.)
        request_params["response_format"] = {"type": "json_object"}

        # Add DeepSeek thinking parameters if enabled
        if self.enable_thinking:
            extra_body: dict = {"thinking": {"type": "enabled"}}
            if self.reasoning_effort:
                extra_body["reasoning_effort"] = self.reasoning_effort
            request_params["extra_body"] = extra_body

        response = self.client.chat.completions.create(**request_params)

        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)
        return output_schema.model_validate(parsed)
