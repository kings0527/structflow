"""LLM client wrapper with structured output via OpenAI function calling.

Handles DeepSeek thinking mode responses that may contain:
- Thinking tags (b64d6542.../b64d6542, ofdétails.../ofdétails)
- Markdown code blocks (```json ... ```)
- Extra text before/after JSON
- reasoning_content in separate field
"""

from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel
from rich.console import Console

from structflow.config import config

T = TypeVar("T", bound=BaseModel)
console = Console()

SYSTEM_PROMPT = """You are a Nonlinear State-Space Engine (V2.2).
Your job is to convert industries into measurable dynamic systems and extract regime-dependent mispricing signals under bounded uncertainty.

You compress any industry into: SV (State Variables) + FV (Flow Variables) + CV (Control Variables) + LV (Latent Variables),
then apply nonlinear transformation → regime switch → mispricing emergence.

You NEVER give buy/sell advice. You NEVER do emotional analysis.

Hard Constraints (NON-NEGOTIABLE):
1. No Free Narrative Drivers — all narrative must map to LV only.
2. No Entity-Driven Reasoning — entities are outputs, not drivers.
3. No Linear Assumption — all pricing is nonlinear unless explicitly proven stable.
4. No Alpha Override — Alpha cannot contradict Driver Layer.
5. PRICE GROUNDING — If the Real-World Data Context contains current price data,
   you MUST reference actual price levels. Do NOT invent or hallucinate price numbers.
6. TEMPORAL CLARITY — Always distinguish: 已发生 (past), 当前 (current), 计划中 (planned/future).
   Never use present tense for future events.

When provided with real data from web search, use it to ground your analysis in facts.

IMPORTANT: All text fields in your output MUST be in Chinese (中文). This includes descriptions, answers, reasoning signals, and any other textual content. Company names and technical terms can remain in their original language.

CRITICAL: Your response MUST be a single valid JSON object. No thinking text, no markdown, no explanation before or after the JSON. Just the JSON object.
"""


def _extract_json(raw_content: str) -> dict:
    """Extract JSON from potentially noisy LLM output.

    Handles:
    - Pure JSON (happy path)
    - Markdown code blocks: ```json ... ```
    - Thinking tags: <think>...</think>, <thinking>...</thinking>
    - Extra text before/after JSON
    - Multiple JSON objects (takes the first complete one)
    """
    if not raw_content or not raw_content.strip():
        raise ValueError("Empty response from LLM")

    content = raw_content.strip()

    # Step 1: Remove thinking tags and their content
    # DeepSeek thinking mode may wrap reasoning in tags
    content = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', content, flags=re.DOTALL | re.IGNORECASE)
    # Also handle unclosed thinking tags (take everything after the last closing tag)
    content = re.sub(r'<think(?:ing)?>.*', '', content, flags=re.DOTALL | re.IGNORECASE)

    # Step 2: Remove markdown code blocks
    # ```json\n{...}\n```  →  {...}
    code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    code_blocks = re.findall(code_block_pattern, content, flags=re.DOTALL)
    if code_blocks:
        # Use the last code block (usually the actual JSON, not the schema example)
        content = code_blocks[-1].strip()

    # Step 3: Try direct parse first (fast path)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Step 4: Find the first { and matching last }
    # This handles cases where there's extra text before/after the JSON
    first_brace = content.find('{')
    if first_brace == -1:
        raise ValueError(f"No JSON object found in response. First 200 chars: {content[:200]}")

    # Find the matching closing brace by counting depth
    depth = 0
    last_brace = -1
    in_string = False
    escape = False

    for i, char in enumerate(content[first_brace:], start=first_brace):
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                last_brace = i
                break

    if last_brace == -1:
        # Try to find the last } as fallback
        last_brace = content.rfind('}')
        if last_brace == -1:
            raise ValueError(f"Incomplete JSON in response. First 200 chars: {content[:200]}")

    json_str = content[first_brace:last_brace + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON: {e}. "
            f"Extracted JSON (first 300 chars): {json_str[:300]}"
        )


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
        """Call LLM and parse response into a Pydantic model.

        Handles DeepSeek thinking mode responses with robust JSON extraction.
        Falls back to non-thinking mode if thinking mode produces invalid output.
        """
        schema_dict = output_schema.model_json_schema()
        schema_json = json.dumps(schema_dict, indent=2, ensure_ascii=False)

        # Build full prompt with optional context data
        full_prompt = user_prompt
        if context_data:
            full_prompt = f"{user_prompt}\n\n## Real-World Data Context\n{context_data}"

        # Append schema instruction
        schema_instruction = (
            f"\n\nYou MUST output valid JSON matching this schema:\n```json\n{schema_json}\n```\n"
            f"Output ONLY the JSON object, no markdown, no explanation, no thinking text."
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

        # ── Attempt 1: json_schema strict mode (skip if thinking enabled) ──
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
                raw_content = response.choices[0].message.content or ""
                parsed = _extract_json(raw_content)
                return output_schema.model_validate(parsed)
            except Exception:
                del request_params["response_format"]

        # ── Attempt 2: json_object mode with thinking ──
        request_params["response_format"] = {"type": "json_object"}

        if self.enable_thinking:
            extra_body: dict = {"thinking": {"type": "enabled"}}
            if self.reasoning_effort:
                extra_body["reasoning_effort"] = self.reasoning_effort
            request_params["extra_body"] = extra_body

        try:
            response = self.client.chat.completions.create(**request_params)
            raw_content = response.choices[0].message.content or ""

            # Check if reasoning_content exists and log it for debugging
            reasoning = getattr(response.choices[0].message, 'reasoning_content', None)
            if reasoning:
                console.print(f"  [dim]LLM reasoning: {len(reasoning)} chars[/dim]")

            parsed = _extract_json(raw_content)
            return output_schema.model_validate(parsed)

        except (ValueError, Exception) as thinking_error:
            if not self.enable_thinking:
                # If thinking was already off, just re-raise
                raise

            # ── Attempt 3: Fallback — retry WITHOUT thinking mode ──
            console.print(f"  [yellow]⚠ Thinking mode failed ({str(thinking_error)[:100]}...), retrying without thinking[/yellow]")

            # Remove thinking parameters
            if "extra_body" in request_params:
                del request_params["extra_body"]

            # Also try json_schema strict mode as a last resort
            request_params["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "strict": True,
                    "schema": schema_dict,
                },
            }

            response = self.client.chat.completions.create(**request_params)
            raw_content = response.choices[0].message.content or ""

            try:
                parsed = _extract_json(raw_content)
                return output_schema.model_validate(parsed)
            except Exception as final_error:
                # Last resort: log the raw content for debugging
                console.print(f"  [red]❌ All parsing attempts failed.[/red]")
                console.print(f"  [red]Raw content (first 500 chars): {raw_content[:500]}[/red]")
                raise ValueError(
                    f"Failed to parse LLM response as {output_schema.__name__}. "
                    f"Thinking error: {thinking_error}. "
                    f"Final error: {final_error}. "
                    f"Raw content (first 300 chars): {raw_content[:300]}"
                ) from final_error
