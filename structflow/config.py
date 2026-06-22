"""Configuration management via pydantic-settings + .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

# Find .env file: check cwd first, then project root
_env_file = Path.cwd() / ".env"
if not _env_file.exists():
    _env_file = Path(__file__).parent.parent / ".env"


class LLMConfig(BaseSettings):
    """LLM provider configuration."""
    model: str = "deepseek-v4-flash"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    enable_thinking: bool = True
    reasoning_effort: str = "high"
    temperature: float = 0.2

    model_config = {"env_prefix": "LLM_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class TavilyConfig(BaseSettings):
    """Tavily search API configuration."""
    api_key: str = ""
    search_depth: str = "advanced"
    max_results: int = 10

    model_config = {"env_prefix": "TAVILY_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class AnySearchConfig(BaseSettings):
    """AnySearch API configuration — complementary search engine."""
    api_key: str = ""
    endpoint: str = "https://api.anysearch.com/mcp"
    max_results: int = 5

    model_config = {"env_prefix": "ANYSEARCH_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class DataConfig(BaseSettings):
    """Data collection configuration."""
    enable_web_search: bool = True
    search_max_results: int = 10
    search_depth: str = "advanced"

    model_config = {"env_prefix": "SEARCH_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class AppConfig(BaseSettings):
    """Application-level configuration."""
    default_output_format: str = "markdown"

    model_config = {"env_prefix": "DEFAULT_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class Config:
    """Unified configuration container."""

    def __init__(self):
        self.llm = LLMConfig()
        self.tavily = TavilyConfig()
        self.anysearch = AnySearchConfig()
        self.data = DataConfig()
        self.app = AppConfig()

    @classmethod
    def load(cls) -> Config:
        """Load configuration from .env file and environment variables."""
        return cls()


# Global config instance
config = Config.load()
