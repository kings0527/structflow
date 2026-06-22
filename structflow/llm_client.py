"""LLM client wrapper with structured output via OpenAI function calling."""

from __future__ import annotations

import json
import os
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

SYSTEM_PROMPT = """You are a Structural Intelligence System.
Your job is to decompose industries into power-flow-risk structures.
You NEVER give buy/sell advice. You NEVER do emotional analysis. You NEVER expand narratives.
You ONLY identify: structure, power distribution, value flows, risk accumulation, and score vectors.
All outputs must be attributed to specific roles (Producer/Payer/Mediator/Controller).
Never write vague descriptions like "platform is strong" — always specify which role controls what.
"""


class LLMClient:
    """Thin wrapper around OpenAI chat completions with structured output."""

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        enable_thinking: bool = False,
        reasoning_effort: str | None = None,
    ):
        self.model = model or os.getenv("STRUCTFLOW_MODEL", "gpt-4o")
        self.enable_thinking = enable_thinking
        self.reasoning_effort = reasoning_effort
        self.client = OpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

    def structured_call(
        self,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.2,
    ) -> T:
        """Call LLM and parse response into a Pydantic model."""
        schema_dict = output_schema.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2, ensure_ascii=False)

        # Append schema instruction to user prompt for models that don't support json_schema strict mode
        schema_instruction = (
            f"\n\nYou MUST output valid JSON matching this schema:\n```json\n{schema_json}\n```\n"
            f"Output ONLY the JSON object, no markdown, no explanation."
        )
        full_prompt = user_prompt + schema_instruction

        # Build request parameters
        request_params: dict = {
            "model": self.model,
            "temperature": temperature,
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
