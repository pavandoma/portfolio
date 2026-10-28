"""Claude via the official Anthropic Python SDK.

Uses structured outputs (``output_config.format``) so responses are schema-valid JSON, and
opts into server-side refusal fallbacks (``fallbacks: "default"``) so a safety-classifier
decline is retried on Anthropic's recommended fallback model instead of failing the request.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic

from app.llm.base import LLMError, LLMRefusal

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"
    is_local = False

    def __init__(self, api_key: str | None, model: str | None = None, timeout_s: float = 60.0,
                 base_url: str | None = None, effort: str = "medium"):
        kwargs: dict[str, Any] = {"timeout": timeout_s, "max_retries": 2}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        # Without an explicit key the SDK resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login`.
        self.client = anthropic.Anthropic(**kwargs)
        self.model = model or DEFAULT_MODEL
        self.effort = effort

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 4000) -> dict[str, Any]:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                # Rewriting and extraction are routine; Claude Opus 5.5 defaults to medium effort,
                # stated explicitly here so the setting is visible and tunable.
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise LLMError("Claude rate limit reached; try again shortly.") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Claude API error {exc.status_code}.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Claude API.") from exc
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise LLMRefusal(f"Claude declined the request (category: {category}).")
        if response.stop_reason == "max_tokens":
            raise LLMError("Claude response was cut off (max_tokens).")
        text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
        if text is None:
            raise LLMError("Claude returned no text content.")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError("Claude returned invalid JSON.") from exc
