"""Provider-independent LLM interface.

Every LLM feature in this application is optional and returns structured JSON validated
against a schema. Outputs are suggestions only: rewritten bullets must still pass the fact
check, and extracted job requirements must quote the posting verbatim, or they are dropped.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMError(RuntimeError):
    pass


class LLMNotConfigured(LLMError):
    pass


class LLMRefusal(LLMError):
    pass


class LLMProvider(Protocol):
    name: str
    model: str
    is_local: bool

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any], max_tokens: int = 4000) -> dict[str, Any]:
        """Return a JSON object that conforms to ``schema``."""
        ...
