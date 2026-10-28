"""Loads validator adapters (built-in + MCP entries from RIP_MCP_CONFIG) and runs them independently."""

from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.schemas.validation import ExternalValidatorResult
from app.validation.adapters.base import ValidationContext
from app.validation.adapters.builtin import InternalPdfParser, PopplerParser
from app.validation.adapters.mcp_adapter import MCPServerConfig, MCPToolAdapter

log = logging.getLogger(__name__)


def load_mcp_configs() -> tuple[list[MCPServerConfig], list[str]]:
    path = get_settings().mcp_config_path
    if not path:
        return [], []
    errors: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], [f"MCP config not found: {path}"]
    except json.JSONDecodeError as exc:
        return [], [f"MCP config is not valid JSON: {exc}"]
    configs = []
    for entry in raw.get("servers", []):
        try:
            configs.append(MCPServerConfig.model_validate(entry))
        except Exception as exc:
            errors.append(f"Invalid MCP entry {entry.get('name', '?')}: {exc}")
    return configs, errors


def get_adapters() -> list:
    adapters: list = [InternalPdfParser(), PopplerParser()]
    configs, _errors = load_mcp_configs()
    adapters.extend(MCPToolAdapter(c) for c in configs)
    return adapters


def describe_adapters() -> list[dict]:
    configs, errors = load_mcp_configs()
    out = []
    for a in get_adapters():
        ok, why = a.availability()
        out.append({"name": a.name, "category": a.category, "available": ok, "detail": why,
                    "sends_data_externally": a.sends_data_externally})
    for e in errors:
        out.append({"name": "mcp-config", "category": "parser", "available": False, "detail": e,
                    "sends_data_externally": False})
    return out


def run_all(ctx: ValidationContext) -> list[ExternalValidatorResult]:
    results = []
    for adapter in get_adapters():
        try:
            results.append(adapter.run(ctx))
        except Exception as exc:  # one adapter must never break the others
            log.warning("validator %s failed: %s", adapter.name, type(exc).__name__)
            results.append(ExternalValidatorResult(adapter=adapter.name, category=adapter.category, status="error",
                                                   detail=f"{type(exc).__name__}: {str(exc)[:200]}"))
    if not any(r.category == "matcher" for r in results):
        results.append(ExternalValidatorResult(
            adapter="external-matcher", category="matcher", status="unavailable",
            detail="No external candidate-job matcher is configured. Internal scores are shown; no external score "
                   "is reported or estimated."))
    return results
