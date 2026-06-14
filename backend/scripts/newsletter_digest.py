#!/usr/bin/env python3
"""Newsletter digest cron job -- Lisa's Assets (Issue #8).

Queries the Lisa's Assets database for newly published reports scoring a
Lisa Coefficient >= 8.0, formats a dark-themed digest email, and dispatches
it as a Listmonk campaign to the *Lisa's Assets Alerts* mailing list.

Usage:
    cd /home/lisa/projects/lisa-assets-arbor/backend
    python scripts/newsletter_digest.py

Behaviour
---------
1. Reads the last-sent watermark from ``.last_newsletter_sent`` (defaults to
   7 days ago when the file is absent).
2. Fetches qualifying reports created after the watermark, ordered by score.
3. Ensures the *Lisa's Assets Alerts* list exists in Listmonk (creates it if
   missing).
4. If there are qualifying reports -> builds the HTML body, creates a
   campaign and starts it.
5. If there are no qualifying reports -> exits silently (no email, no
   watermark change).
6. Advances the watermark to the newest report that was processed.

Notes
-----
* Listmonk v6 uses session-cookie auth (server-rendered login form), **not**
  HTTP basic auth. This script performs the login handshake and reuses the
  session cookie for all ``/api`` calls.
* Database access is via ``docker exec supabase-db psql`` -- the documented
  access path -- which sidesteps the Supavisor tenant-prefix requirement.
* ``httpx`` is the only third-party dependency (already in requirements.txt).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

import httpx

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BACKEND_DIR = Path(__file__).resolve().parent.parent
WATERMARK_FILE = BACKEND_DIR / ".last_newsletter_sent"

LISTMONK_BASE_URL = os.getenv("LISTMONK_BASE_URL", "http://localhost:9000")
LISTMONK_USER = os.getenv("LISTMONK_USER", "cryptosi")
LISTMONK_PASS = os.getenv("LISTMONK_PASS", "LisaKim2026!")

LIST_NAME = "Lisa's Assets Alerts"
CAMPAIGN_FROM_EMAIL = os.getenv(
    "LISTMONK_FROM_EMAIL", "Lisa Kim <newsletter@webarastudio.com>"
)
CAMPAIGN_TEMPLATE_ID = int(os.getenv("LISTMONK_TEMPLATE_ID", "1"))
APP_BASE_URL = os.getenv("LISA_APP_BASE_URL", "https://lisa-assets-app.vercel.app")

MIN_COEFFICIENT = 8.0
DEFAULT_LOOKBACK_DAYS = 7

# Dark theme palette
COLOUR_BG = "#111111"
COLOUR_PANEL = "#1c1c1c"
COLOUR_ACCENT = "#e7f900"
COLOUR_TEXT = "#f5f5f5"
COLOUR_MUTED = "#9a9a9a"

# Subprocess / network budgets
PSQL_TIMEOUT = 30
HTTP_TIMEOUT = 30.0

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("newsletter_digest")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def parse_dt(value: str) -> datetime:
    """Parse an ISO-8601-ish timestamp into an aware UTC datetime."""
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_dt(dt: datetime) -> str:
    """Format a datetime as a compact ISO string for storage/comparison."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


# --------------------------------------------------------------------------- #
# Watermark (last-sent timestamp) persistence
# --------------------------------------------------------------------------- #
def read_watermark() -> datetime:
    """Return the watermark timestamp, defaulting to N days ago if absent."""
    try:
        raw = WATERMARK_FILE.read_text().strip()
        if raw:
            return parse_dt(raw)
        log.warning("Watermark file empty; defaulting to %d days ago.",
                    DEFAULT_LOOKBACK_DAYS)
    except FileNotFoundError:
        log.info("No watermark file; defaulting to %d days ago.",
                 DEFAULT_LOOKBACK_DAYS)
    except Exception as exc:  # malformed contents
        log.warning("Could not parse watermark (%s); defaulting to %d days ago.",
                    exc, DEFAULT_LOOKBACK_DAYS)
    return datetime.now(timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def write_watermark(dt: datetime) -> None:
    WATERMARK_FILE.write_text(fmt_dt(dt) + "\n")


# --------------------------------------------------------------------------- #
# Database access (docker exec -> psql -> JSON)
# --------------------------------------------------------------------------- #
PSQL_CONTAINER = "supabase-db"


def _psql_json(sql: str) -> Any:
    """Run ``sql`` inside the Supabase DB container, returning parsed JSON.

    The query must return a single scalar JSON value (json/jsonb aggregate).
    """
    cmd = [
        "docker", "exec", PSQL_CONTAINER,
        "psql", "-U", "postgres", "-d", "postgres",
        "-tA",  # unaligned, no column headers
        "-c", sql,
    ]
    log.debug("psql: %s", sql)
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=PSQL_TIMEOUT
        )
    except FileNotFoundError:
        raise RuntimeError("'docker' not found on PATH -- cannot reach DB")
    except subprocess.TimeoutExpired:
        raise RuntimeError("DB query timed out")

    if proc.returncode != 0:
        raise RuntimeError(
            f"psql failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
    out = proc.stdout.strip()
    if not out:
        return []
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not decode DB JSON: {exc}\nraw={out!r}")


def query_reports(since: datetime) -> list[dict]:
    """Return qualifying reports (>= MIN_COEFFICIENT) created after ``since``."""
    since_lit = since.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f+00:00"
    )
    sql = f"""
SELECT COALESCE(json_agg(t ORDER BY t.lisa_coefficient DESC), '[]'::json)
FROM (
    SELECT r.id,
           r.lisa_coefficient,
           r.lisa_verdict,
           r.strongest_agent,
           to_char(r.created_at AT TIME ZONE 'UTC',
                   'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS created_at,
           p.name,
           p.symbol,
           p.coingecko_id,
           p.logo_url
    FROM reports r
    JOIN projects p ON p.id = r.project_id
    WHERE r.status = 'public'
      AND r.lisa_coefficient >= {MIN_COEFFICIENT:g}
      AND r.created_at > '{since_lit}'::timestamptz
    ORDER BY r.lisa_coefficient DESC
) t;
""".strip()
    rows = _psql_json(sql)
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected DB payload: {rows!r}")
    return rows


# --------------------------------------------------------------------------- #
# Listmonk client (session-cookie auth)
# --------------------------------------------------------------------------- #
class ListmonkError(RuntimeError):
    pass


class ListmonkClient:
    """Thin wrapper around the Listmonk v6 REST API.

    Authenticates via the server-rendered login form (which sets a session
    cookie) and reuses that cookie for every subsequent ``/api`` request.
    """

    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=False)
        self._login(username, password)

    # -- lifecycle ---------------------------------------------------------- #
    def _login(self, username: str, password: str) -> None:
        # Fetch the login page to obtain the CSRF nonce (if present).
        page = self._client.get(f"{self.base_url}/admin")
        nonce = ""
        if page.status_code == 200:
            m = re.search(r'name="nonce"\s+value="([^"]+)"', page.text)
            if m:
                nonce = m.group(1)

        form = {"username": username, "password": password, "next": "/admin"}
        if nonce:
            form["nonce"] = nonce

        resp = self._client.post(
            f"{self.base_url}/admin/login", data=form
        )
        if resp.status_code != 302 or "session" not in self._client.cookies:
            raise ListmonkError(
                f"Listmonk login failed (status={resp.status_code}); "
                f"check LISTMONK_USER/LISTMONK_PASS credentials"
            )
        log.info("Authenticated to Listmonk as %s", username)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ListmonkClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- low-level API helper ---------------------------------------------- #
    def _api(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._client.request(method, url, **kwargs)
        if resp.status_code >= 400:
            raise ListmonkError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:300]}"
            )
        try:
            return resp.json()
        except ValueError:
            return {}

    # -- domain operations -------------------------------------------------- #
    def ensure_list(self, name: str, *, list_type: str = "public",
                    optin: str = "single") -> int:
        """Return the id of ``name``, creating it if it does not exist."""
        data = self._api("GET", "/api/lists")
        for entry in data.get("data", {}).get("results", []):
            if entry.get("name") == name:
                log.info("List %r already exists (id=%s)", name, entry["id"])
                return int(entry["id"])

        created = self._api(
            "POST", "/api/lists",
            json={"name": name, "type": list_type, "optin": optin},
        )
        list_id = int(created["data"]["id"])
        log.info("Created list %r (id=%s)", name, list_id)
        return list_id

    def create_campaign(self, *, name: str, subject: str, list_ids: list[int],
                        body: str) -> int:
        payload = {
            "name": name,
            "subject": subject,
            "lists": list_ids,
            "type": "regular",
            "content_type": "richtext",
            "body": body,
            "messenger": "email",
            "from_email": CAMPAIGN_FROM_EMAIL,
            "template_id": CAMPAIGN_TEMPLATE_ID,
        }
        data = self._api("POST", "/api/campaigns", json=payload)
        campaign_id = int(data["data"]["id"])
        log.info("Created campaign %r (id=%s)", name, campaign_id)
        return campaign_id

    def start_campaign(self, campaign_id: int) -> None:
        self._api(
            "PUT",
            f"/api/campaigns/{campaign_id}/status",
            json={"status": "running"},
        )
        log.info("Started campaign id=%s", campaign_id)


# --------------------------------------------------------------------------- #
# Email rendering
# --------------------------------------------------------------------------- #
def _verdict_snippet(verdict: str | None, limit: int = 160) -> str:
    if not verdict:
        return ""
    text = verdict.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "…"


def render_email(reports: list[dict]) -> str:
    """Build the dark-themed HTML digest body for the given reports."""
    today = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    count = len(reports)

    cards: list[str] = []
    for idx, r in enumerate(reports, start=1):
        name = escape(str(r.get("name") or "Unknown"))
        symbol = escape(str(r.get("symbol") or ""))
        coeff_raw = r.get("lisa_coefficient")
        try:
            coeff_str = f"{float(coeff_raw):.2f}" if coeff_raw is not None else "—"
        except (TypeError, ValueError):
            coeff_str = "—"
        agent = escape(str(r.get("strongest_agent") or "—"))
        verdict = _verdict_snippet(r.get("lisa_verdict"))
        coingecko_id = (r.get("coingecko_id") or "").strip()
        link = escape(f"{APP_BASE_URL.rstrip('/')}/project/{coingecko_id}")
        logo = (r.get("logo_url") or "").strip()

        logo_html = ""
        if logo:
            logo_html = (
                f'<img src="{escape(logo)}" alt="{name}" '
                f'style="width:44px;height:44px;border-radius:50%;'
                f'object-fit:cover;vertical-align:middle;"/>'
            )

        cards.append(f"""
<div style="background:{COLOUR_PANEL};border:1px solid #2a2a2a;border-radius:14px;
padding:22px;margin-bottom:16px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
    {logo_html}
    <div>
      <div style="font-size:18px;font-weight:700;color:{COLOUR_TEXT};">{name}
        <span style="color:{COLOUR_MUTED};font-weight:600;">${symbol}</span>
      </div>
      <div style="font-size:12px;color:{COLOUR_MUTED};">#{idx} pick</div>
    </div>
  </div>
  <div style="margin:8px 0 12px;">
    <span style="font-size:34px;font-weight:800;color:{COLOUR_ACCENT};
      letter-spacing:-0.5px;">{coeff_str}</span>
    <span style="font-size:13px;color:{COLOUR_MUTED};margin-left:6px;">
      Lisa Coefficient
    </span>
  </div>
  <div style="font-size:13px;color:{COLOUR_MUTED};margin-bottom:6px;">
    Strongest agent: <span style="color:{COLOUR_TEXT};font-weight:600;">{agent}</span>
  </div>
  {f'<div style="font-size:14px;color:{COLOUR_TEXT};line-height:1.5;margin-bottom:14px;">{escape(verdict)}</div>' if verdict else ''}
  <a href="{link}" style="display:inline-block;background:{COLOUR_ACCENT};
    color:#111;text-decoration:none;font-weight:700;font-size:13px;
    padding:9px 16px;border-radius:8px;">View full report →</a>
</div>
""".strip())

    cards_html = "\n".join(cards)

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lisa's Top Picks</title></head>
<body style="margin:0;padding:0;background:{COLOUR_BG};
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
    style="background:{COLOUR_BG};">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0">
        <tr><td style="text-align:center;padding-bottom:28px;">
          <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;
            color:{COLOUR_ACCENT};font-weight:700;margin-bottom:8px;">
            Lisa's Top Picks
          </div>
          <h1 style="margin:0 0 6px;font-size:30px;font-weight:800;color:{COLOUR_TEXT};
            letter-spacing:-0.5px;">{count} project{'' if count == 1 else 's'} scoring 8.0+</h1>
          <p style="margin:0;color:{COLOUR_MUTED};font-size:14px;">{escape(today)}</p>
        </td></tr>
        <tr><td>
          {cards_html}
        </td></tr>
        <tr><td style="padding-top:24px;text-align:center;">
          <p style="margin:0;color:{COLOUR_MUTED};font-size:12px;line-height:1.6;">
            Lisa's Assets · Automated intelligence digest<br/>
            You're receiving this because you subscribed to Lisa's Assets Alerts.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def run() -> int:
    since = read_watermark()
    log.info("Watermark: %s", fmt_dt(since))

    reports = query_reports(since)
    log.info("Found %d qualifying report(s) (>= %.1f) since the watermark.",
             len(reports), MIN_COEFFICIENT)

    if not reports:
        log.info("No qualifying reports; exiting silently (no email sent).")
        return 0

    with ListmonkClient(LISTMONK_BASE_URL, LISTMONK_USER, LISTMONK_PASS) as lm:
        list_id = lm.ensure_list(LIST_NAME)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        campaign_id = lm.create_campaign(
            name=f"Lisa's Top Picks - {date_str}",
            subject=f"Lisa found {len(reports)} project"
                    f"{'' if len(reports) == 1 else 's'} scoring 8.0+",
            list_ids=[list_id],
            body=render_email(reports),
        )
        lm.start_campaign(campaign_id)

    # Advance the watermark to the newest report we just processed.
    newest = max(parse_dt(r["created_at"]) for r in reports)
    write_watermark(newest)
    log.info("Watermark advanced to %s.", fmt_dt(newest))
    log.info("Done: campaign id=%s dispatched to list id=%s (%d report(s)).",
             campaign_id, list_id, len(reports))
    return 0


def main() -> int:
    try:
        return run()
    except ListmonkError as exc:
        log.error("Listmonk error: %s", exc)
        return 2
    except Exception as exc:  # noqa: BLE001 -- cron must not raise
        log.exception("Newsletter digest failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
