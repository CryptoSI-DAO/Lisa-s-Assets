"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache

try:
    # python-dotenv is optional at runtime — handy for local dev
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv missing is fine
    pass


class Settings:
    """Settings sourced from environment variables.

    Kept as a plain class (rather than pydantic.BaseSettings) so the backend
    boots even if pydantic-settings is not installed.
    """

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )

    # CoinGecko
    COINGECKO_API_BASE: str = os.getenv(
        "COINGECKO_API_BASE", "https://api.coingecko.com/api/v3"
    )

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "http://localhost:8000")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")

    # Misc
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))
    REQUEST_TIMEOUT_SECONDS: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))

    @property
    def async_database_url(self) -> str:
        """Return the DATABASE_URL in asyncpg-compatible form."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
