"""Token balance verification for LISA / SOONAK / CRDD discounts.

Reads on-chain ERC-20 (EVM) and SPL (Solana) token balances using only
JSON-RPC + httpx (no web3.py / solana-py dependency).

Tokens checked by :func:`check_token_discount`:
  * ``LISA``  — ERC-20 on Base
  * ``SOONAK`` — SPL token on Solana
  * ``CRDD``  — ERC-20 on Arbitrum

If a wallet holds >= ``DISCOUNT_THRESHOLD`` (default 10 000) of *any* of the
three tokens, the 50% discount applies.

Contract/mint addresses are sourced from env vars (see :mod:`app.config`).
They default to empty strings — populate them before going live.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

# ERC-20 balanceOf(address) function selector (first 4 bytes of keccak256).
BALANCE_OF_SELECTOR = "0x70a08231"

# Default token decimals. ERC-20 LISA/CRDD are 18; SPL SOONAK assumed 9.
EVM_DECIMALS = 18
SOLANA_DECIMALS = 9

# Discount policy (kept in sync with services.payment).
DISCOUNT_RATE = 0.5  # 50% off


# ---------------------------------------------------------------------------
# EVM (Base / Arbitrum)
# ---------------------------------------------------------------------------
async def _evm_rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    """Single JSON-RPC POST to an EVM endpoint."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            rpc_url, json=payload, headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def _encode_balance_of(wallet_address: str) -> str:
    """Encode a balanceOf(address) call.

    selector (4 bytes) + zero-padded 32-byte address = 4 + 64 hex chars.
    """
    addr = wallet_address.strip()
    if addr.startswith("0x") or addr.startswith("0X"):
        addr = addr[2:]
    addr = addr.lower().rjust(64, "0")
    return BALANCE_OF_SELECTOR + addr


async def get_evm_token_balance(
    wallet_address: str, token_contract: str, rpc_url: str
) -> float:
    """Return the human-readable ERC-20 balance of ``wallet_address``.

    Uses ``eth_call`` to the token contract's ``balanceOf(address)`` and
    decodes the returned uint256, scaling by 10**18. Returns 0.0 on any
    error so that discount checks fail safe.
    """
    wallet_address = (wallet_address or "").strip()
    token_contract = (token_contract or "").strip()
    if not wallet_address or not token_contract:
        return 0.0

    data = _encode_balance_of(wallet_address)
    try:
        result = await _evm_rpc_call(
            rpc_url,
            "eth_call",
            [{"to": token_contract, "data": data}, "latest"],
        )
    except Exception as exc:
        logger.warning(
            "EVM balance lookup failed (%s @ %s): %s",
            token_contract, rpc_url, exc,
        )
        return 0.0

    return _decode_evm_amount(result)


def _decode_evm_amount(result: Optional[str]) -> float:
    """Decode an eth_call uint256 hex result into a scaled float."""
    if not result:
        return 0.0
    try:
        raw = int(str(result), 16)
    except (TypeError, ValueError):
        return 0.0
    return raw / (10 ** EVM_DECIMALS)


# ---------------------------------------------------------------------------
# Solana (SPL)
# ---------------------------------------------------------------------------
async def _solana_rpc_call(
    rpc_url: str, method: str, params: list[Any]
) -> Any:
    """Single JSON-RPC POST to a Solana endpoint."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            rpc_url, json=payload, headers={"Content-Type": "application/json"}
        )
        resp.raise_for_status()
        data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"Solana RPC error: {data['error']}")
    return data.get("result")


async def get_solana_token_balance(
    wallet_address: str, mint_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com"
) -> float:
    """Return the human-readable SPL token balance of a Solana wallet.

    Calls ``getTokenAccountsByOwner`` with a mint filter to find the
    associated token account(s), then sums their ``tokenAmount.uiAmount``.
    Returns 0.0 on any error.
    """
    wallet_address = (wallet_address or "").strip()
    mint_address = (mint_address or "").strip()
    if not wallet_address or not mint_address:
        return 0.0

    try:
        result = await _solana_rpc_call(
            rpc_url,
            "getTokenAccountsByOwner",
            [
                wallet_address,
                {"mint": mint_address},
                {"encoding": "jsonParsed"},
            ],
        )
    except Exception as exc:
        logger.warning(
            "Solana balance lookup failed (%s @ %s): %s",
            mint_address, rpc_url, exc,
        )
        return 0.0

    return _sum_solana_balances(result)


def _sum_solana_balances(result: Any) -> float:
    """Sum uiAmount across all returned token accounts."""
    if not result or not isinstance(result, dict):
        return 0.0
    accounts = result.get("value") or []
    total = 0.0
    for acct in accounts:
        try:
            parsed = acct.get("account", {}).get("data", {}).get("parsed", {})
            info = parsed.get("info", {}) if isinstance(parsed, dict) else {}
            amount_obj = info.get("tokenAmount") or {}
            ui = amount_obj.get("uiAmount")
            if ui is not None:
                total += float(ui)
        except (TypeError, ValueError, AttributeError):
            continue
    return total


# ---------------------------------------------------------------------------
# Unified discount check
# ---------------------------------------------------------------------------
async def check_token_discount(wallet_address: str) -> dict[str, Any]:
    """Check all three discount tokens for ``wallet_address``.

    Returns::

        {
            "discounted": bool,
            "tokens_held": {"lisa": float, "soonak": float, "crdd": float},
            "discount_rate": 0.5,   # when discounted, else 0.0
            "threshold": 10000.0,
            "qualifying_token": "lisa" | "soonak" | "crdd" | None,
        }

    A wallet qualifies if it holds >= ``DISCOUNT_THRESHOLD`` of *any* token.
    """
    settings = get_settings()
    threshold = settings.DISCOUNT_THRESHOLD

    # Run the three balance lookups. Each is wrapped to fail safe (→ 0.0).
    try:
        lisa = await get_evm_token_balance(
            wallet_address, settings.LISA_TOKEN_CONTRACT, settings.BASE_RPC_URL
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("LISA balance check failed: %s", exc)
        lisa = 0.0

    try:
        soonak = await get_solana_token_balance(
            wallet_address, settings.SOONAK_MINT, settings.SOLANA_RPC_URL
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("SOONAK balance check failed: %s", exc)
        soonak = 0.0

    try:
        crdd = await get_evm_token_balance(
            wallet_address, settings.CRDD_TOKEN_CONTRACT, settings.ARBITRUM_RPC_URL
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("CRDD balance check failed: %s", exc)
        crdd = 0.0

    tokens_held = {"lisa": lisa, "soonak": soonak, "crdd": crdd}

    qualifying = None
    if lisa >= threshold:
        qualifying = "lisa"
    elif soonak >= threshold:
        qualifying = "soonak"
    elif crdd >= threshold:
        qualifying = "crdd"

    return {
        "discounted": qualifying is not None,
        "tokens_held": tokens_held,
        "discount_rate": DISCOUNT_RATE if qualifying else 0.0,
        "threshold": threshold,
        "qualifying_token": qualifying,
    }
