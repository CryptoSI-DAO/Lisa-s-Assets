"""Async database connection layer (asyncpg).

Provides a lazily-initialised connection pool and helper functions for use
inside FastAPI dependency injection. The pool connects to the local Supabase
PostgreSQL instance.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import asyncpg

from .config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> asyncpg.Pool:
    """Create the global connection pool (idempotent)."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    dsn = _to_asyncpg_dsn(settings.DATABASE_URL)

    logger.info("Creating asyncpg pool → %s", _redact(dsn))
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    return _pool


async def close_pool() -> None:
    """Close the global pool, if open."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the current pool (must be initialised first)."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_pool() first")
    return _pool


# ---------------------------------------------------------------------------
# Helper query utilities
# ---------------------------------------------------------------------------
async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Run a SELECT and return all rows."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    """Run a SELECT and return a single row (or None)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    """Run a query and return a single scalar value."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Run an INSERT/UPDATE/DELETE, return the status string."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


def _to_asyncpg_dsn(url: str) -> str:
    """Normalise a SQLAlchemy-style URL into a plain postgres:// DSN for asyncpg.

    asyncpg accepts `postgresql://...` or `postgres://...` but **not** the
    `postgresql+asyncpg://...` driver-prefix that SQLAlchemy uses.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres+asyncpg://"):
        return url.replace("postgres+asyncpg://", "postgresql://", 1)
    return url


def _redact(dsn: str) -> str:
    """Hide the password in a DSN for safe logging."""
    try:
        if "@" in dsn:
            head, tail = dsn.split("@", 1)
            if ":" in head:
                user, _pw = head.rsplit(":", 1)
                return f"{user}:***@{tail}"
    except Exception:
        pass
    return dsn
