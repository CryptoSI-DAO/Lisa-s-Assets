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

    # Payments (Base / USDC)
    BASE_RPC_URL: str = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
    USDC_CONTRACT_BASE: str = os.getenv(
        "USDC_CONTRACT_BASE", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    )
    # Wallet that report payments should be sent to. Leave as the placeholder
    # default until a production receive address is provisioned.
    PAYMENT_RECEIVE_ADDRESS: str = os.getenv(
        "PAYMENT_RECEIVE_ADDRESS", "0xLISA_RECEIVE_ADDRESS_TBD"
    )
    # When False, report generation works without a verified payment (MVP / demo
    # mode). Flip to True once paid access goes live.
    PAYMENT_REQUIRED: bool = os.getenv("PAYMENT_REQUIRED", "false").lower() == "true"

    # Discount tokens (LISA / SOONAK / CRDD). Contract/mint addresses are left
    # empty by default — populate via env vars before going live.
    LISA_TOKEN_CONTRACT: str = os.getenv("LISA_TOKEN_CONTRACT", "")  # Base
    SOONAK_MINT: str = os.getenv("SOONAK_MINT", "")  # Solana SPL mint
    CRDD_TOKEN_CONTRACT: str = os.getenv("CRDD_TOKEN_CONTRACT", "")  # Arbitrum
    ARBITRUM_RPC_URL: str = os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc")
    SOLANA_RPC_URL: str = os.getenv(
        "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"
    )
    DISCOUNT_THRESHOLD: float = float(os.getenv("DISCOUNT_THRESHOLD", "10000"))

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
