"""OpenAI-compatible chat completions with JSON-schema structured output, plus a local Ollama provider."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.llm.base import LLMError, LLMRefusal


class OpenAIProvider:
    name = "openai"
    is_local = False

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", timeout_s: float = 60.0,
                 transport: httpx.BaseTransport | None = None):
        if not model:
            raise LLMError("Set LLM_MODEL to the OpenAI model you want to use.")
        self.model = model
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport,
                                   headers={"Authorization": f"Bearer {api_key}"})

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 4000) -> dict[str, Any]:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "result", "schema": schema, "strict": True}},
            "max_completion_tokens": max_tokens,
        }
        try:
            r = self.client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the OpenAI API.") from exc
        if r.status_code >= 400:
            raise LLMError(f"OpenAI API error {r.status_code}.")
        choice = r.json()["choices"][0]
        message = choice.get("message", {})
        if message.get("refusal"):
            raise LLMRefusal("The model declined the request.")
        try:
            return json.loads(message.get("content") or "")
        except json.JSONDecodeError as exc:
            raise LLMError("Model returned invalid JSON.") from exc


class OllamaProvider:
    """Local model through Ollama. Data stays on this machine."""

    name = "ollama"
    is_local = True

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None):
        if not model:
            raise LLMError("Set LLM_MODEL to a local Ollama model (for example 'llama3.1').")
        self.model = model
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s, transport=transport)

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 4000) -> dict[str, Any]:
        body = {
            "model": self.model, "stream": False, "format": schema,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        try:
            r = self.client.post("/api/chat", json=body)
        except httpx.HTTPError as exc:
            raise LLMError("Could not reach the local Ollama server.") from exc
        if r.status_code >= 400:
            raise LLMError(f"Ollama error {r.status_code}.")
        try:
            return json.loads(r.json()["message"]["content"])
        except (KeyError, json.JSONDecodeError) as exc:
            raise LLMError("Local model returned invalid JSON.") from exc
