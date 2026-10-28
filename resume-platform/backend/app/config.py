"""Application settings, read from environment variables (and an optional .env file).

Secrets (API keys) are only ever read from the environment. They are never logged:
see ``app.core.logging`` for the redaction filter.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PLATFORM_DIR = BACKEND_DIR.parent
DEFAULT_DATA_DIR = PLATFORM_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PLATFORM_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage -----------------------------------------------------------------
    data_dir: Path = Field(default=DEFAULT_DATA_DIR, alias="RIP_DATA_DIR")
    # SQLite by default (local-first). Docker Compose sets a PostgreSQL URL.
    database_url: str = Field(default="", alias="DATABASE_URL")

    # HTTP server -------------------------------------------------------------
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="RIP_CORS_ORIGINS")
    # Optional shared token. When set, every /api request must send
    # "Authorization: Bearer <token>". Recommended for any non-localhost deployment.
    api_token: SecretStr | None = Field(default=None, alias="RIP_API_TOKEN")

    # Upload limits -----------------------------------------------------------
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, alias="RIP_MAX_UPLOAD_BYTES")
    max_pdf_pages: int = Field(default=20, alias="RIP_MAX_PDF_PAGES")
    max_text_chars: int = Field(default=200_000, alias="RIP_MAX_TEXT_CHARS")

    # URL fetching ------------------------------------------------------------
    fetch_timeout_s: float = Field(default=15.0, alias="RIP_FETCH_TIMEOUT_S")
    fetch_max_bytes: int = Field(default=3 * 1024 * 1024, alias="RIP_FETCH_MAX_BYTES")
    # Only for tests / trusted local setups: allow fetching private network addresses.
    fetch_allow_private: bool = Field(default=False, alias="RIP_FETCH_ALLOW_PRIVATE")
    firecrawl_api_key: SecretStr | None = Field(default=None, alias="FIRECRAWL_API_KEY")
    firecrawl_base_url: str = Field(default="https://api.firecrawl.dev", alias="FIRECRAWL_BASE_URL")
    github_token: SecretStr | None = Field(default=None, alias="GITHUB_TOKEN")

    # LLM ---------------------------------------------------------------------
    # "none" keeps every pipeline deterministic and offline.
    llm_provider: Literal["none", "anthropic", "openai", "ollama"] = Field(default="none", alias="LLM_PROVIDER")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    llm_timeout_s: float = Field(default=60.0, alias="LLM_TIMEOUT_S")
    # Resume data never leaves the machine unless this is explicitly enabled.
    # A local Ollama model does not need it.
    allow_external_data_sharing: bool = Field(default=False, alias="RIP_ALLOW_EXTERNAL_DATA_SHARING")

    # Validators / MCP ----------------------------------------------------------
    mcp_config_path: Path | None = Field(default=None, alias="RIP_MCP_CONFIG")

    # Resume generation ---------------------------------------------------------
    max_revision_cycles: int = Field(default=3, alias="RIP_MAX_REVISION_CYCLES")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'resume_platform.db').as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.uploads_dir, self.outputs_dir):
            d.mkdir(parents=True, exist_ok=True)
            try:
                d.chmod(0o700)
            except OSError:  # pragma: no cover - e.g. mounted volumes
                pass


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
