"""NFT agent-card generation — SVG-based visual export for reports.

Each card is a standalone SVG with a dark background, neon-yellow accents,
and an agent-emoji avatar. The strongest agent gets a gold border + TOP ANALYST
badge. Lisa Kim's card gets a special crown-gradient background.
"""

from __future__ import annotations

from datetime import datetime

# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------
agents_meta: dict[str, dict[str, str]] = {
    "truth_seeker": {"name": "TruthSeeker", "emoji": "🎯"},
    "maven_metrics": {"name": "MavenMetrics", "emoji": "📊"},
    "token_logic": {"name": "TokenLogic", "emoji": "💰"},
    "liquid_edge": {"name": "LiquidEdge", "emoji": "🌊"},
    "hype_pulse": {"name": "HypePulse", "emoji": "🔥"},
    "code_crafter": {"name": "CodeCrafter", "emoji": "👨‍💻"},
    "risk_eye": {"name": "RiskEye", "emoji": "⚠️"},
    "lisa_kim": {"name": "Lisa Kim", "emoji": "👑"},
}

# Map the camelCase DB agent names → snake_case keys in ``agents_meta``.
_AGENT_DB_KEY_MAP: dict[str, str] = {
    "truthSeeker": "truth_seeker",
    "mavenMetrics": "maven_metrics",
    "tokenLogic": "token_logic",
    "liquidEdge": "liquid_edge",
    "hypePulse": "hype_pulse",
    "codeCrafter": "code_crafter",
    "riskEye": "risk_eye",
    "lisaKim": "lisa_kim",
}


def resolve_agent_meta(agent_key: str) -> dict[str, str]:
    """Resolve an agent key (snake_case *or* camelCase) to its metadata.

    Falls back to a generic entry if the key is unknown.
    """
    snake = _AGENT_DB_KEY_MAP.get(agent_key, agent_key)
    return agents_meta.get(
        snake,
        {"name": agent_key.replace("_", " ").title() or "Agent", "emoji": "🤖"},
    )


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_BG = "#111111"
_BG_LIGHT = "#1a1a1a"
_NEON = "#e7f900"
_TEXT = "#f0f0f0"
_TEXT_DIM = "#888888"
_GOLD = "#ffd700"

# ---------------------------------------------------------------------------
# SVG builder
# ---------------------------------------------------------------------------
_CARD_W = 600
_CARD_H = 800


def generate_agent_card_svg(
    *,
    agent_name: str,
    agent_emoji: str,
    project_name: str,
    project_symbol: str,
    coefficient: float,
    verdict: str,
    date_str: str,
    strongest: bool = False,
) -> str:
    """Return SVG string for an agent card.

    Parameters
    ----------
    strongest:
        When ``True`` the card gets a gold border + "TOP ANALYST" badge.
    """
    is_lisa = "lisa" in agent_name.lower()

    # ── Background ─────────────────────────────────────────────────────────
    if is_lisa:
        bg_defs = _crown_gradient_defs()
        bg_rect = (
            f'<rect width="{_CARD_W}" height="{_CARD_H}" '
            f'fill="url(#crownGradient)" />'
        )
    else:
        bg_defs = ""
        bg_rect = (
            f'<rect width="{_CARD_W}" height="{_CARD_H}" fill="{_BG}" />'
        )

    # ── Decorative border ──────────────────────────────────────────────────
    border_color = _GOLD if strongest else _NEON
    border_w = 4 if strongest else 2
    border = (
        f'<rect x="10" y="10" width="{_CARD_W - 20}" height="{_CARD_H - 20}" '
        f'rx="20" fill="none" stroke="{border_color}" '
        f'stroke-width="{border_w}" />'
    )
    inner_border = (
        f'<rect x="22" y="22" width="{_CARD_W - 44}" height="{_CARD_H - 44}" '
        f'rx="14" fill="none" stroke="{_NEON}" stroke-width="0.5" '
        f'opacity="0.3" />'
    )

    # ── TOP ANALYST badge ──────────────────────────────────────────────────
    badge = ""
    if strongest:
        bx = _CARD_W // 2 - 80
        badge = (
            f'<g transform="translate({bx}, 70)">'
            f'<rect width="160" height="30" rx="15" fill="{_GOLD}" />'
            f'<text x="80" y="20" text-anchor="middle" '
            f'font-family="monospace" font-size="13" font-weight="bold" '
            f'fill="#111111">★ TOP ANALYST</text>'
            f"</g>"
        )

    # ── Corner accent lines ────────────────────────────────────────────────
    accents = _corner_accents()

    # ── Agent emoji avatar (large circle) ─────────────────────────────────
    avatar_y = 190 if not strongest else 210
    avatar = (
        f'<circle cx="{_CARD_W // 2}" cy="{avatar_y}" r="60" '
        f'fill="{_BG_LIGHT}" stroke="{_NEON}" stroke-width="2" />'
        f'<text x="{_CARD_W // 2}" y="{avatar_y + 24}" text-anchor="middle" '
        f'font-size="64">{agent_emoji}</text>'
    )

    # ── Agent name ─────────────────────────────────────────────────────────
    agent_label_y = avatar_y + 105
    agent_name_text = (
        f'<text x="{_CARD_W // 2}" y="{agent_label_y}" text-anchor="middle" '
        f'font-family="monospace" font-size="26" font-weight="bold" '
        f'fill="{_NEON}">{_escape(agent_name)}</text>'
    )

    # ── Project name + symbol ─────────────────────────────────────────────
    project_y = agent_label_y + 50
    project_text = (
        f'<text x="{_CARD_W // 2}" y="{project_y}" text-anchor="middle" '
        f'font-family="monospace" font-size="20" fill="{_TEXT}">'
        f'{_escape(project_name)}</text>'
        f'<text x="{_CARD_W // 2}" y="{project_y + 28}" text-anchor="middle" '
        f'font-family="monospace" font-size="14" fill="{_TEXT_DIM}">'
        f'$ {_escape(project_symbol)}</text>'
    )

    # ── Lisa Coefficient score (large) ────────────────────────────────────
    score_block_y = project_y + 100
    score_label = (
        f'<text x="{_CARD_W // 2}" y="{score_block_y}" text-anchor="middle" '
        f'font-family="monospace" font-size="13" fill="{_TEXT_DIM}" '
        f'letter-spacing="2">LISA COEFFICIENT</text>'
    )
    coeff_str = f"{coefficient:.1f}"
    score_num = (
        f'<text x="{_CARD_W // 2}" y="{score_block_y + 75}" text-anchor="middle" '
        f'font-family="monospace" font-size="72" font-weight="bold" '
        f'fill="{_NEON}">{coeff_str}</text>'
    )
    score_unit = (
        f'<text x="{_CARD_W // 2}" y="{score_block_y + 100}" text-anchor="middle" '
        f'font-family="monospace" font-size="16" fill="{_TEXT_DIM}">/ 10</text>'
    )

    # ── Verdict ───────────────────────────────────────────────────────────
    verdict_y = score_block_y + 140
    verdict_text = (
        f'<text x="{_CARD_W // 2}" y="{verdict_y}" text-anchor="middle" '
        f'font-family="monospace" font-size="16" fill="{_TEXT}">'
        f'{_escape(verdict)}</text>'
    )

    # ── Footer: date ──────────────────────────────────────────────────────
    footer_y = _CARD_H - 50
    date_text = (
        f'<text x="{_CARD_W // 2}" y="{footer_y}" text-anchor="middle" '
        f'font-family="monospace" font-size="12" fill="{_TEXT_DIM}">'
        f'{_escape(date_str)}</text>'
    )
    brand_text = (
        f'<text x="{_CARD_W // 2}" y="{footer_y + 20}" text-anchor="middle" '
        f'font-family="monospace" font-size="10" fill="{_TEXT_DIM}" '
        f'opacity="0.5">LISA&apos;S ASSETS</text>'
    )

    svg = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{_CARD_W}" height="{_CARD_H}" \
viewBox="0 0 {_CARD_W} {_CARD_H}">
<defs>
{bg_defs}
</defs>
{bg_rect}
{border}
{inner_border}
{accents}
{badge}
{avatar}
{agent_name_text}
{project_text}
{score_label}
{score_num}
{score_unit}
{verdict_text}
{date_text}
{brand_text}
</svg>
"""
    return svg


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
def _crown_gradient_defs() -> str:
    """Special gradient background for Lisa Kim's card."""
    return (
        '<linearGradient id="crownGradient" x1="0%" y1="0%" x2="100%" y2="100%">'
        f'<stop offset="0%" stop-color="#2a1a00" />'
        f'<stop offset="40%" stop-color="#111111" />'
        f'<stop offset="70%" stop-color="#1a1500" />'
        f'<stop offset="100%" stop-color="#0d0d0d" />'
        "</linearGradient>"
        '<radialGradient id="crownGlow" cx="50%" cy="30%" r="50%">'
        f'<stop offset="0%" stop-color="{_GOLD}" stop-opacity="0.12" />'
        '<stop offset="100%" stop-color="#ffd700" stop-opacity="0" />'
        "</radialGradient>"
    )


def _corner_accents() -> str:
    """Decorative neon-yellow corner brackets."""
    s = 40  # bracket arm length
    m = 10  # margin from card edge
    w = 3   # stroke width
    c = _NEON
    lines = [
        # top-left
        f'<line x1="{m}" y1="{m + s}" x2="{m}" y2="{m}" stroke="{c}" stroke-width="{w}" />',
        f'<line x1="{m}" y1="{m}" x2="{m + s}" y2="{m}" stroke="{c}" stroke-width="{w}" />',
        # top-right
        f'<line x1="{_CARD_W - m - s}" y1="{m}" x2="{_CARD_W - m}" y2="{m}" stroke="{c}" stroke-width="{w}" />',
        f'<line x1="{_CARD_W - m}" y1="{m}" x2="{_CARD_W - m}" y2="{m + s}" stroke="{c}" stroke-width="{w}" />',
        # bottom-left
        f'<line x1="{m}" y1="{_CARD_H - m - s}" x2="{m}" y2="{_CARD_H - m}" stroke="{c}" stroke-width="{w}" />',
        f'<line x1="{m}" y1="{_CARD_H - m}" x2="{m + s}" y2="{_CARD_H - m}" stroke="{c}" stroke-width="{w}" />',
        # bottom-right
        f'<line x1="{_CARD_W - m - s}" y1="{_CARD_H - m}" x2="{_CARD_W - m}" y2="{_CARD_H - m}" stroke="{c}" stroke-width="{w}" />',
        f'<line x1="{_CARD_W - m}" y1="{_CARD_H - m}" x2="{_CARD_W - m}" y2="{_CARD_H - m - s}" stroke="{c}" stroke-width="{w}" />',
    ]
    return "\n".join(lines)


def _escape(text: str) -> str:
    """XML-escape ampersands and angle brackets for SVG text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Convenience: build a card from a report row
# ---------------------------------------------------------------------------
def today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")
