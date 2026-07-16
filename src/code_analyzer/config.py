"""
Centralised, layered configuration.

Precedence (highest wins):
    CLI flags  >  environment variables (ANALYZER_*)  >  YAML config file  >  defaults

Using ``pydantic-settings`` gives us typed, validated config with a single source
of truth, and keeps secrets (the API key) out of code and version control.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Rough public pricing (USD per 1M tokens) for cost *estimation* only.
# Kept here so it is easy to update; not a billing source of truth.
MODEL_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}

DEFAULT_SOURCE_EXTENSIONS = [
    ".java", ".kt", ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rb",
    ".cs", ".cpp", ".c", ".h", ".hpp", ".rs", ".php", ".scala", ".swift",
]

# Directories that are never worth sending to an LLM.
DEFAULT_EXCLUDE_DIRS = [
    ".git", ".github", "build", "dist", "out", "target", "node_modules",
    ".gradle", ".idea", ".mvn", "__pycache__", ".venv", "venv", "vendor",
    "gradle", "test", "tests",  # skip test sources by default; toggle with include_tests
]


class Settings(BaseSettings):
    """All tunable knobs live here."""

    model_config = SettingsConfigDict(
        env_prefix="ANALYZER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # allow both field name and alias (ANTHROPIC_API_KEY)
    )

    # --- Secrets ---
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    # Optional: point at a proxy / reseller endpoint. Leave unset for official Anthropic.
    anthropic_base_url: str | None = Field(default=None, alias="ANTHROPIC_BASE_URL")

    # --- Model / LLM behaviour ---
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.0  # deterministic extraction
    max_output_tokens: int = 8192
    max_input_tokens: int = 150_000  # safety budget below the model's context window

    # --- Concurrency & resilience ---
    max_concurrency: int = 6
    max_retries: int = 4

    # --- Ingestion ---
    source_extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_SOURCE_EXTENSIONS))
    exclude_dirs: list[str] = Field(default_factory=lambda: list(DEFAULT_EXCLUDE_DIRS))
    include_tests: bool = False
    max_file_bytes: int = 400_000  # skip vendored blobs / generated giants
    max_files: int | None = None  # cap for quick/cheap runs

    # --- Chunking ---
    chunk_token_budget: int = 12_000  # per-file input budget before we split

    # --- Caching ---
    cache_enabled: bool = True
    cache_dir: Path = Path(".analyzer_cache")

    # --- Output / logging ---
    output_path: Path = Path("out/analysis.json")
    log_level: str = "INFO"

    # --- Modes ---
    dry_run: bool = False  # run the full pipeline with a heuristic stand-in (no API key)

    # --- Security ---
    redact_secrets: bool = True  # scrub credentials from code before sending to the LLM

    def pricing(self) -> dict:
        return MODEL_PRICING.get(self.model, {"input": 3.00, "output": 15.00})

    @classmethod
    def load(cls, config_file: Path | None = None, **overrides) -> Settings:
        """
        Build settings from (optional) YAML file + env + explicit overrides.

        ``overrides`` are CLI values; ``None`` entries are dropped so they don't
        clobber lower-precedence layers.
        """
        file_values: dict = {}
        if config_file and Path(config_file).exists():
            file_values = yaml.safe_load(Path(config_file).read_text()) or {}

        clean_overrides = {k: v for k, v in overrides.items() if v is not None}
        # env is read automatically by BaseSettings; file + CLI layered on top.
        return cls(**{**file_values, **clean_overrides})
