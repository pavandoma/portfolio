"""Generic MCP tool adapter for external resume parsers / matchers.

Each external service is described in a JSON config file (RIP_MCP_CONFIG). Nothing is sent
unless the entry has ``allow_resume_data: true`` *and* the platform-wide
RIP_ALLOW_EXTERNAL_DATA_SHARING setting is on (local stdio tools that keep data on the
machine can set ``local_only: true`` instead). Scores are read only from the tool's response,
via ``score_path``; if the tool returns none, no score is reported.

Example entry::

    {
      "name": "my-resume-parser",
      "category": "parser",
      "transport": "stdio",
      "command": "python", "args": ["-m", "some_resume_mcp"],
      "tool": "parse_resume",
      "arguments": {"resume_text": "{resume_text}"},
      "score_path": "score",
      "allow_resume_data": true,
      "local_only": true
    }
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.validation import ExternalValidatorResult
from app.validation.adapters.base import ValidationContext


class MCPServerConfig(BaseModel):
    name: str
    category: str = "parser"  # parser | matcher
    transport: str = "stdio"  # stdio | http
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    score_path: str | None = None
    allow_resume_data: bool = False
    local_only: bool = False
    enabled: bool = True
    timeout_s: float = 45.0
    notes: str = ""


def _fill(template: Any, values: dict[str, str]) -> Any:
    if isinstance(template, str):
        out = template
        for k, v in values.items():
            out = out.replace("{" + k + "}", v)
        return out
    if isinstance(template, dict):
        return {k: _fill(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [_fill(v, values) for v in template]
    return template


def _dig(obj: Any, path: str | None) -> Any:
    if not path:
        return None
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


class MCPToolAdapter:
    sends_data_externally = True

    def __init__(self, cfg: MCPServerConfig):
        self.cfg = cfg
        self.name = f"mcp:{cfg.name}"
        self.category = cfg.category if cfg.category in ("parser", "matcher") else "parser"
        self.sends_data_externally = not cfg.local_only

    def availability(self) -> tuple[bool, str]:
        if not self.cfg.enabled:
            return False, "Disabled in config"
        if self.cfg.transport == "stdio" and not self.cfg.command:
            return False, "No command configured"
        if self.cfg.transport == "http" and not self.cfg.url:
            return False, "No URL configured"
        return True, f"Configured ({self.cfg.transport})"

    def _authorized(self) -> tuple[bool, str]:
        if not self.cfg.allow_resume_data:
            return False, "Sending resume data to this tool is not authorized (allow_resume_data is false)."
        if self.sends_data_externally and not get_settings().allow_external_data_sharing:
            return False, "External data sharing is off (RIP_ALLOW_EXTERNAL_DATA_SHARING=false)."
        return True, ""

    async def _call(self, arguments: dict) -> Any:
        from mcp import Client
        from mcp.client.stdio import StdioServerParameters

        if self.cfg.transport == "stdio":
            env = {k: os.path.expandvars(v) for k, v in self.cfg.env.items()}
            target: Any = StdioServerParameters(command=self.cfg.command, args=self.cfg.args, env=env or None)
        else:
            target = self.cfg.url
        async with Client(target, read_timeout_seconds=self.cfg.timeout_s) as client:
            tools = await client.list_tools()
            names = [t.name for t in getattr(tools, "tools", tools)]
            if self.cfg.tool not in names:
                raise LookupError(f"Tool '{self.cfg.tool}' not offered by server (has: {', '.join(names)})")
            return await client.call_tool(self.cfg.tool, arguments)

    def run(self, ctx: ValidationContext) -> ExternalValidatorResult:
        ok, why = self.availability()
        if not ok:
            return ExternalValidatorResult(adapter=self.name, category=self.category, status="unavailable", detail=why)
        allowed, why = self._authorized()
        if not allowed:
            return ExternalValidatorResult(adapter=self.name, category=self.category, status="not_authorized", detail=why)
        args = _fill(self.cfg.arguments, {"resume_text": ctx.resume_text, "job_text": ctx.job_text,
                                          "job_title": ctx.job.title if ctx.job else ""})
        try:
            result = asyncio.run(asyncio.wait_for(self._call(args), timeout=self.cfg.timeout_s))
        except Exception as exc:  # unreachable server, protocol error, timeout ...
            return ExternalValidatorResult(adapter=self.name, category=self.category, status="unavailable",
                                           detail=f"Could not reach the MCP server: {type(exc).__name__}: {str(exc)[:200]}")
        payload: Any = result.structured_content
        if payload is None:
            texts = [getattr(c, "text", "") for c in result.content if getattr(c, "text", None)]
            joined = "\n".join(texts)
            try:
                payload = json.loads(joined)
            except (json.JSONDecodeError, TypeError):
                payload = {"text": joined[:4000]}
        if result.is_error:
            return ExternalValidatorResult(adapter=self.name, category=self.category, status="error",
                                           detail=str(payload)[:300], raw=payload if isinstance(payload, dict) else None)
        score = _dig(payload, self.cfg.score_path)
        numeric = float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None
        return ExternalValidatorResult(
            adapter=self.name, category=self.category, status="ok", score=numeric,
            detail="Response received" + ("" if numeric is not None else "; the tool returned no numeric score"),
            raw=payload if isinstance(payload, dict) else {"value": payload},
        )
