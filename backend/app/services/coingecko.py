"""Async CoinGecko API client with in-memory caching and 429 retry.

Issue #3: CoinGecko integration.

Public surface:
    search_projects(query)          → list[{coingecko_id, name, symbol, logo_url}]
    get_project(coingecko_id)       → full project payload
    get_top_projects(limit=50)      → top projects by market cap
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory TTL cache: {cache_key: (timestamp, payload)}
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL: float = 3600.0  # 1 hour
_CACHE_LOCK = asyncio.Lock()


def _cache_get(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    ts, payload = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: Any) -> None:
    _CACHE[key] = (time.time(), payload)


def clear_cache() -> None:
    """Clear the entire in-memory cache (handy for tests)."""
    _CACHE.clear()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class CoinGeckoClient:
    """Thin async wrapper around the CoinGecko v3 REST API."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        settings = get_settings()
        self.base_url = (base_url or settings.COINGECKO_API_BASE).rstrip("/")
        self.timeout = timeout or settings.REQUEST_TIMEOUT_SECONDS
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "CoinGeckoClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "accept": "application/json",
                    "user-agent": "lisas-assets-backend/0.1",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Low-level GET with caching + 429 retry
    # ------------------------------------------------------------------
    async def _get(self, path: str, params: Optional[dict[str, Any]] = None,
                   cache_key: Optional[str] = None, max_retries: int = 3) -> Any:
        if cache_key:
            cached = _cache_get(cache_key)
            if cached is not None:
                logger.debug("CoinGecko cache hit: %s", cache_key)
                return cached

        client = await self._ensure_client()
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt < max_retries:
            attempt += 1
            try:
                resp = await client.get(path, params=params)
                if resp.status_code == 429:
                    backoff = min(2 ** attempt, 16)
                    logger.warning(
                        "CoinGecko rate limited (429), retrying in %ss (attempt %d/%d)",
                        backoff, attempt, max_retries,
                    )
                    await asyncio.sleep(backoff)
                    continue
                resp.raise_for_status()
                data = resp.json()
                if cache_key:
                    _cache_set(cache_key, data)
                return data
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code
                if status in (502, 503, 504) and attempt < max_retries:
                    backoff = min(2 ** attempt, 16)
                    logger.warning("CoinGecko %d, retrying in %ss", status, backoff)
                    await asyncio.sleep(backoff)
                    continue
                raise
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    backoff = min(2 ** attempt, 16)
                    logger.warning("CoinGecko request error (%s), retrying in %ss",
                                   exc, backoff)
                    await asyncio.sleep(backoff)
                    continue
                raise
        # Exhausted retries
        raise last_exc or RuntimeError("CoinGecko request failed")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def search_projects(self, query: str) -> list[dict[str, Any]]:
        """Search CoinGecko for projects matching `query`.

        Returns a normalised list of {coingecko_id, name, symbol, logo_url}.
        """
        if not query or not query.strip():
            return []
        query = query.strip()
        cache_key = f"search:{query.lower()}"
        try:
            data = await self._get("/search", {"query": query}, cache_key=cache_key)
        except Exception as exc:
            logger.error("CoinGecko search failed: %s", exc)
            return []

        coins = data.get("coins", []) if isinstance(data, dict) else []
        results: list[dict[str, Any]] = []
        for c in coins:
            item = c.get("item", c)
            results.append({
                "coingecko_id": item.get("id"),
                "name": item.get("name"),
                "symbol": (item.get("symbol") or "").upper(),
                "logo_url": item.get("large") or item.get("thumb") or item.get("logo"),
                "market_cap_rank": item.get("market_cap_rank"),
            })
        return results

    async def get_project(self, coingecko_id: str,
                          localization: bool = False) -> dict[str, Any]:
        """Fetch full detail for a single project by CoinGecko id."""
        cache_key = f"project:{coingecko_id}"
        params = {
            "tickers": "false",
            "market_data": "true",
            "community_data": "false",
            "developer_data": "false",
            "sparkline": "false",
            "localization": "true" if localization else "false",
        }
        data = await self._get(f"/coins/{coingecko_id}", params, cache_key=cache_key)
        market = data.get("market_data", {}) or {}
        image = data.get("image", {}) or {}
        desc = data.get("description", {}) or {}
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "symbol": (data.get("symbol") or "").upper(),
            "logo": image.get("large") or image.get("small"),
            "price_usd": _safe_float(market.get("current_price", {}).get("usd")),
            "market_cap_usd": _safe_float(market.get("market_cap", {}).get("usd")),
            "description": desc.get("en") if isinstance(desc, dict) else None,
            "rank": data.get("market_cap_rank"),
            "coingecko_id": data.get("id"),
        }

    async def get_top_projects(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the top `limit` projects by market cap."""
        limit = max(1, min(int(limit), 250))
        cache_key = f"top:{limit}"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        data = await self._get("/coins/markets", params, cache_key=cache_key)
        if not isinstance(data, list):
            return []
        results: list[dict[str, Any]] = []
        for c in data:
            results.append({
                "coingecko_id": c.get("id"),
                "name": c.get("name"),
                "symbol": (c.get("symbol") or "").upper(),
                "logo_url": c.get("image"),
                "price_usd": _safe_float(c.get("current_price")),
                "market_cap_usd": _safe_float(c.get("market_cap")),
                "rank": c.get("market_cap_rank"),
                "change_24h": _safe_float(c.get("price_change_percentage_24h")),
            })
        return results


# ---------------------------------------------------------------------------
# Module-level convenience functions (reuse a lazily-created singleton client)
# ---------------------------------------------------------------------------
_singleton: Optional[CoinGeckoClient] = None


def _get_singleton() -> CoinGeckoClient:
    global _singleton
    if _singleton is None:
        _singleton = CoinGeckoClient()
    return _singleton


async def search_projects(query: str) -> list[dict[str, Any]]:
    return await _get_singleton().search_projects(query)


async def get_project(coingecko_id: str) -> dict[str, Any]:
    return await _get_singleton().get_project(coingecko_id)


async def get_top_projects(limit: int = 50) -> list[dict[str, Any]]:
    return await _get_singleton().get_top_projects(limit)


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
