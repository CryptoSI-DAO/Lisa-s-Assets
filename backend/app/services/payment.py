"""Payment service — pricing, checkout sessions, and on-chain verification.

Real USDC payment verification on Base. A tx hash is looked up against a Base
RPC endpoint via JSON-RPC (``eth_getTransactionReceipt``); the receipt's logs
are inspected for a USDC ``Transfer`` event matching the expected sender and
amount.

Only httpx is required (no web3.py dependency), keeping the deploy small.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
REPORT_PRICE_USD: float = 9.99
DISCOUNT_TOKEN_THRESHOLD: float = 10_000.0  # $LISA tokens for discount
DISCOUNT_RATE: float = 0.5  # 50% off

# USDC uses 6 decimals (so 9.99 USDC == 9_990_000 raw units).
USDC_DECIMALS: int = 6

# keccak256("Transfer(address,address,uint256)") — well-known ERC-20 topic.
# Hard-coded so we need no crypto dependency.
TRANSFER_EVENT_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


def compute_price(wallet_address: str | None, token_balance: float = 0.0) -> dict[str, Any]:
    """Compute the price for a single report, applying any token discount."""
    discount_applied = token_balance >= DISCOUNT_TOKEN_THRESHOLD
    amount = REPORT_PRICE_USD
    if discount_applied:
        amount *= DISCOUNT_RATE
    return {
        "amount": round(amount, 2),
        "currency": "USDC",
        "chain": "base",
        "discount_applied": discount_applied,
        "discount_rate": DISCOUNT_RATE if discount_applied else 0.0,
    }


def create_checkout(*, report_id: str | None, coingecko_id: str | None,
                    wallet_address: str, amount: float, token: str,
                    chain: str) -> dict[str, Any]:
    """Build a checkout payload addressed to the configured receive wallet."""
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    return {
        "checkout_id": str(uuid.uuid4()),
        "report_id": report_id,
        "coingecko_id": coingecko_id,
        "wallet_address": wallet_address,
        "amount": amount,
        "token": token,
        "chain": chain,
        "expires_at": expires.isoformat(),
        "status": "awaiting_payment",
        "payment_address": settings.PAYMENT_RECEIVE_ADDRESS,
    }


# ---------------------------------------------------------------------------
# On-chain verification (Base USDC)
# ---------------------------------------------------------------------------
async def _rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    """Send a single JSON-RPC POST to an EVM RPC endpoint."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(rpc_url, json=payload,
                                 headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    if "error" in data and data["error"]:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result")


def _topic_to_address(topic: str) -> str:
    """Decode a 32-byte topic into a 0x-prefixed checksum-less lowercase address."""
    # Topic is 0x + 64 hex chars; the address is the last 40 hex chars.
    return "0x" + topic[-40:].lower()


def _decode_usdc_transfer(log: dict, expected_usdc: str) -> Optional[dict[str, Any]]:
    """If ``log`` is a USDC Transfer, return {from, to, value}, else None."""
    topics = log.get("topics") or []
    if len(topics) < 3:
        return None
    if (log.get("address") or "").lower() != expected_usdc.lower():
        return None
    if topics[0].lower() != TRANSFER_EVENT_TOPIC:
        return None
    try:
        value = int(log.get("data", "0x0"), 16)
    except (TypeError, ValueError):
        return None
    return {
        "from": _topic_to_address(topics[1]),
        "to": _topic_to_address(topics[2]),
        "value": value,
    }


async def verify_payment(*, tx_hash: str, wallet_address: str, amount: float,
                         token: str, chain: str, report_id: str | None = None,
                         discount_applied: bool = False) -> dict[str, Any]:
    """Verify a USDC payment on Base by inspecting the on-chain receipt.

    Checks performed:
      * chain is ``base`` and token is ``USDC``;
      * the transaction exists and succeeded (status 0x1);
      * the receipt contains a USDC ``Transfer`` event;
      * the transfer sender matches ``wallet_address``;
      * the transferred amount (6-decimal) is >= the requested ``amount``;
      * (if a real receive address is configured) the recipient matches it.

    On success a ``payments`` row is upserted (tx_hash is unique).
    """
    tx_hash = (tx_hash or "").strip()
    wallet = (wallet_address or "").strip().lower()

    base = {
        "verified": False,
        "tx_hash": tx_hash,
        "message": "",
    }

    if not tx_hash:
        base["message"] = "Missing tx_hash."
        return base

    if chain.lower() != "base":
        base["message"] = f"On-chain verification only supports 'base', got '{chain}'."
        return base
    if token.upper() != "USDC":
        base["message"] = f"Only USDC payments are supported, got '{token}'."
        return base

    settings = get_settings()
    rpc_url = settings.BASE_RPC_URL
    usdc = settings.USDC_CONTRACT_BASE

    expected_raw = round(float(amount) * (10 ** USDC_DECIMALS))

    # 1. Fetch the transaction receipt.
    try:
        receipt = await _rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash])
    except Exception as exc:
        logger.warning("Base RPC receipt lookup failed for %s: %s", tx_hash, exc)
        base["message"] = f"Could not reach Base RPC: {exc}"
        return base

    if not receipt:
        base["message"] = (
            "Transaction not found on Base. It may not be confirmed yet — "
            "retry in a few seconds."
        )
        return base

    if str(receipt.get("status", "")).lower() != "0x1":
        base["message"] = "Transaction reverted on-chain — payment not valid."
        return base

    # 2. Find a matching USDC Transfer log.
    matching = None
    for log in receipt.get("logs", []):
        decoded = _decode_usdc_transfer(log, usdc)
        if not decoded:
            continue
        if decoded["from"] != wallet:
            continue
        if decoded["value"] < expected_raw:
            continue
        # Optional recipient check (only if a real receive address is set).
        receive = settings.PAYMENT_RECEIVE_ADDRESS.lower()
        if receive.startswith("0x") and len(receive) == 42:
            if decoded["to"] != receive:
                continue
        matching = decoded
        break

    if matching is None:
        base["message"] = (
            "No matching USDC transfer found in this transaction "
            "(check sender, amount, and recipient)."
        )
        return base

    # 3. Persist / update the payment row.
    try:
        from .. import db  # local import to avoid circulars at module load
        await db.execute(
            """
            INSERT INTO payments
                (report_id, wallet_address, amount, token, chain,
                 tx_hash, discount_applied, verified)
            VALUES ($1, $2, $3, $4, $5, $6, $7, TRUE)
            ON CONFLICT (tx_hash) DO UPDATE
              SET verified = TRUE,
                  wallet_address = EXCLUDED.wallet_address,
                  amount = EXCLUDED.amount
            """,
            report_id, wallet_address, float(amount), token.upper(), chain.lower(),
            tx_hash, discount_applied,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to persist verified payment %s: %s", tx_hash, exc)

    base.update({
        "verified": True,
        "amount_raw": matching["value"],
        "amount_usdc": round(matching["value"] / (10 ** USDC_DECIMALS), 6),
        "from": matching["from"],
        "to": matching["to"],
        "message": (
            f"Payment verified on Base: {matching['value'] / 10 ** USDC_DECIMALS:.6f} "
            f"USDC from {matching['from']}."
        ),
    })
    return base
