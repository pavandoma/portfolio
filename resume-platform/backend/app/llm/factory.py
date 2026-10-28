"""Select the configured LLM provider, enforcing the external-data-sharing setting."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.llm.base import LLMNotConfigured, LLMProvider


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the provider, or None when LLM features are off (the default)."""
    s = settings or get_settings()
    if s.llm_provider == "none":
        return None
    if s.llm_provider == "ollama":
        from app.llm.openai_provider import OllamaProvider

        return OllamaProvider(model=s.llm_model, base_url=s.ollama_base_url, timeout_s=s.llm_timeout_s)
    if not s.allow_external_data_sharing:
        raise LLMNotConfigured(
            f"LLM_PROVIDER={s.llm_provider} would send resume text to an external API. Set "
            "RIP_ALLOW_EXTERNAL_DATA_SHARING=true to allow it, or use LLM_PROVIDER=ollama for a local model.")
    if s.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        key = s.anthropic_api_key.get_secret_value() if s.anthropic_api_key else None
        return AnthropicProvider(api_key=key, model=s.llm_model or None, timeout_s=s.llm_timeout_s)
    if s.llm_provider == "openai":
        from app.llm.openai_provider import OpenAIProvider

        if not s.openai_api_key:
            raise LLMNotConfigured("OPENAI_API_KEY is not set.")
        return OpenAIProvider(api_key=s.openai_api_key.get_secret_value(), model=s.llm_model,
                              base_url=s.openai_base_url, timeout_s=s.llm_timeout_s)
    raise LLMNotConfigured(f"Unknown LLM provider {s.llm_provider}")


def describe(settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    info = {"provider": s.llm_provider, "model": s.llm_model or None,
            "external_data_sharing": s.allow_external_data_sharing, "available": False, "detail": ""}
    if s.llm_provider == "none":
        info["detail"] = "LLM features are off; everything runs deterministically and offline."
        return info
    try:
        p = get_provider(s)
        info.update(available=p is not None, model=getattr(p, "model", None), detail="Configured")
    except Exception as exc:
        info["detail"] = str(exc)
    return info
