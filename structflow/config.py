"""Configuration management via pydantic-settings + .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM provider configuration."""
    model: str = "deepseek-v4-flash"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    enable_thinking: bool = True
    reasoning_effort: str = "high"
    temperature: float = 0.2

    model_config = {"env_prefix": "LLM_"}


class TavilyConfig(BaseSettings):
    """Tavily search API configuration."""
    api_key: str = ""
    search_depth: str = "advanced"
    max_results: int = 10

    model_config = {"env_prefix": "TAVILY_"}


class DataConfig(BaseSettings):
    """Data collection configuration."""
    enable_web_search: bool = True
    search_max_results: int = 10
    search_depth: str = "advanced"

    model_config = {"env_prefix": "SEARCH_"}


class AppConfig(BaseSettings):
    """Application-level configuration."""
    default_output_format: str = "markdown"

    model_config = {"env_prefix": "DEFAULT_"}


class Config:
    """Unified configuration container."""

    def __init__(self):
        self.llm = LLMConfig()
        self.tavily = TavilyConfig()
        self.data = DataConfig()
        self.app = AppConfig()

    @classmethod
    def load(cls) -> Config:
        """Load configuration from .env file and environment variables."""
        return cls()


# Global config instance
config = Config.load()
