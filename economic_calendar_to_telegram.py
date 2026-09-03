#!/usr/bin/env python3
"""
Daily medium/high-impact economic calendar -> Telegram.

Pulls the Forex Factory weekly calendar feed (the same source FTMO's own
calendar widget uses), filters down to today's Medium/High impact events in
a chosen timezone, and posts a formatted digest to Telegram. On Mondays,
also sends a week-ahead overview of all Mon-Fri events first.

Env vars required:
    TELEGRAM_BOT_TOKEN   - token from @BotFather
    TELEGRAM_CHAT_ID     - your user id, group id, or channel id

Optional:
    CALENDAR_TIMEZONE    - IANA tz name, default "Europe/Helsinki"
    MIN_IMPACT           - "medium" (default, includes High) or "high" (High only)
    NO_TRADE_WINDOW_MIN  - minutes before/after each event to avoid trading, default 5
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
TZ_NAME = os.environ.get("CALENDAR_TIMEZONE", "Europe/Helsinki")
MIN_IMPACT = os.environ.get("MIN_IMPACT", "medium").lower()
NO_TRADE_WINDOW_MIN = int(os.environ.get("NO_TRADE_WINDOW_MIN", "5"))

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
    window = NO_TRADE_WINDOW_MIN
    header = (
        f"*Economic Calendar — Medium/High Impact*\n{date_label} ({TZ_NAME})\n"
        f"⛔ _No-trade window: {window} min before/after each event below_"
    )

    blocks = []
    for e in events:
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        time_str = dt.strftime("%H:%M")
        window_start = (dt - timedelta(minutes=window)).strftime("%H:%M")
        window_end = (dt + timedelta(minutes=window)).strftime("%H:%M")
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
        line += f"\n   ⛔ no-trade `{window_start}–{window_end}`"
        blocks.append(line)

    return header + "\n\n" + "\n\n".join(blocks)


def in_scope_week(event, monday, friday):
    impact = event.get("impact", "").lower()
    rank = IMPACT_ORDER.get(impact, -1)
    threshold = IMPACT_ORDER.get(MIN_IMPACT, 1)
    if rank < threshold:
        return False

    raw_date = event.get("date")
    if not raw_date:
        return False
    dt = datetime.fromisoformat(raw_date).astimezone(TZ)
    return monday <= dt.date() <= friday


def format_weekly_digest(events, monday, friday):
    if not events:
        return None

    events = sorted(events, key=lambda e: datetime.fromisoformat(e["date"]))
    window = NO_TRADE_WINDOW_MIN
    week_label = f"{monday.strftime('%d %b')} – {friday.strftime('%d %b %Y')}"
    header = (
        f"*Week Ahead — Medium/High Impact*\n{week_label} ({TZ_NAME})\n"
        f"⛔ _No-trade window: {window} min before/after each event below_"
    )

    by_day = {}
    for e in events:
        dt = datetime.fromisoformat(e["date"]).astimezone(TZ)
        by_day.setdefault(dt.date(), []).append((dt, e))

    day_blocks = []
    for day in sorted(by_day.keys()):
        day_label = day.strftime("%A, %d %B")
        event_lines = []
        for dt, e in by_day[day]:
            time_str = dt.strftime("%H:%M")
            window_start = (dt - timedelta(minutes=window)).strftime("%H:%M")
            window_end = (dt + timedelta(minutes=window)).strftime("%H:%M")
            impact = e.get("impact", "").lower()
            emoji = IMPACT_EMOJI.get(impact, "⚪")
            currency = e.get("country", "")
            title = e.get("title", "Untitled").replace("*", "").replace("_", "")

            line = f"{emoji} `{time_str}` *{currency}* — {title}"
            line += f"\n   ⛔ no-trade `{window_start}–{window_end}`"
            event_lines.append(line)

        day_blocks.append(f"*{day_label}*\n\n" + "\n\n".join(event_lines))

    return header + "\n\n" + "\n\n".join(day_blocks)


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

    # Monday: also send a week-ahead overview of all Mon-Fri events first.
    if today_local.weekday() == 0:
        monday = today_local
        friday = monday + timedelta(days=4)
        week_scoped = [e for e in events if in_scope_week(e, monday, friday)]
        weekly_digest = format_weekly_digest(week_scoped, monday, friday)
        if weekly_digest:
            send_telegram_message(weekly_digest)
            print(f"Sent weekly overview with {len(week_scoped)} event(s).")

    scoped = [e for e in events if in_scope(e, today_local)]
    digest = format_digest(scoped, today_local)

    if digest is None:
        print("No medium/high impact events today - nothing sent.")
        return

    send_telegram_message(digest)
    print(f"Sent {len(scoped)} event(s).")


if __name__ == "__main__":
    main()
