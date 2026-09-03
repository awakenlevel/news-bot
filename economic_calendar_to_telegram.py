#!/usr/bin/env python3
"""
Daily medium/high-impact economic calendar -> Telegram.

Pulls the Forex Factory weekly calendar feed (the same source FTMO's own
calendar widget uses), filters down to today's Medium/High impact events in
a chosen timezone, and posts a formatted digest to Telegram.

Env vars required:
    TELEGRAM_BOT_TOKEN   - token from @BotFather
    TELEGRAM_CHAT_ID     - your user id, group id, or channel id

Optional:
    CALENDAR_TIMEZONE    - IANA tz name, default "Europe/Helsinki"
    MIN_IMPACT           - "medium" (default, includes High) or "high" (High only)
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TZ_NAME = os.environ.get("CALENDAR_TIMEZONE", "Europe/Helsinki")
MIN_IMPACT = os.environ.get("MIN_IMPACT", "medium").lower()

IMPACT_ORDER = {"low": 0, "medium": 1, "high": 2, "holiday": -1}
IMPACT_EMOJI = {"medium": "🟠", "high": "🔴"}

TZ = ZoneInfo(TZ_NAME)


def fetch_events():
    resp = requests.get(FEED_URL, timeout=20)
    resp.raise_for_status()
    return resp.json()


def in_scope(event, today_local):
    impact = event.get("impact", "").lower()
    rank = IMPACT_ORDER.get(impact, -1)
    threshold = IMPACT_ORDER.get(MIN_IMPACT, 1)
    if rank < threshold:
        return False

    raw_date = event.get("date")
    if not raw_date:
        return False
    dt = datetime.fromisoformat(raw_date).astimezone(TZ)
    return dt.date() == today_local


def format_digest(events, today_local):
    if not events:
        return None

    events = sorted(events, key=lambda e: datetime.fromisoformat(e["date"]))
    date_label = today_local.strftime("%A, %d %B %Y")
    lines = [f"*Economic Calendar — Medium/High Impact*\n{date_label} ({TZ_NAME})\n"]

    for e in events:
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        time_str = dt.strftime("%H:%M")
        impact = e.get("impact", "").lower()
        emoji = IMPACT_EMOJI.get(impact, "⚪")
        currency = e.get("country", "")
        title = e.get("title", "Untitled").replace("*", "").replace("_", "")
        forecast = e.get("forecast", "")
        previous = e.get("previous", "")

        line = f"{emoji} `{time_str}` *{currency}* — {title}"
        extra = []
        if forecast:
            extra.append(f"f: {forecast}")
        if previous:
            extra.append(f"p: {previous}")
        if extra:
            line += f"  _({', '.join(extra)})_"
        lines.append(line)

    return "\n".join(lines)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [text[i:i + 3800] for i in range(0, len(text), 3800)]
    for chunk in chunks:
        resp = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        if not resp.ok:
            print(f"[error] Telegram send failed: {resp.status_code} {resp.text}")
        resp.raise_for_status()


def main():
    today_local = datetime.now(TZ).date()
    events = fetch_events()
    scoped = [e for e in events if in_scope(e, today_local)]
    digest = format_digest(scoped, today_local)

    if digest is None:
        print("No medium/high impact events today - nothing sent.")
        return

    send_telegram_message(digest)
    print(f"Sent {len(scoped)} event(s).")


if __name__ == "__main__":
    main()
