"""Optional evidence-provider configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

# Find .env file: check cwd first, then project root
_env_file = Path.cwd() / ".env"
if not _env_file.exists():
    _env_file = Path(__file__).parent.parent / ".env"


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


class MarketDataConfig(BaseSettings):
    """Structured market data channel (accuracy-first, fail-closed)."""
    enabled: bool = True
    timeout: float = 20.0
    price_tolerance: float = 0.005
    lookback_days: int = 365
    enable_dbnomics: bool = True

    model_config = {"env_prefix": "MARKET_DATA_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class FredConfig(BaseSettings):
    """FRED official macro data API (free key, optional)."""
    api_key: str = ""

    model_config = {"env_prefix": "FRED_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class EiaConfig(BaseSettings):
    """EIA official energy data API (free key, optional)."""
    api_key: str = ""

    model_config = {"env_prefix": "EIA_", "env_file": str(_env_file) if _env_file.exists() else None, "extra": "ignore"}


class Config:
    """Unified configuration container."""

    def __init__(self):
        self.tavily = TavilyConfig()
        self.anysearch = AnySearchConfig()
        self.data = DataConfig()
        self.market_data = MarketDataConfig()
        self.fred = FredConfig()
        self.eia = EiaConfig()

    @classmethod
    def load(cls) -> Config:
        """Load configuration from .env file and environment variables."""
        return cls()


# Global config instance
config = Config.load()
