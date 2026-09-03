#!/usr/bin/env python3
"""
Pre-market news digest -> Telegram.

Fetches recent items from a list of RSS feeds, filters by recency (and
optionally by keyword/ticker), dedupes against previously-sent items,
and posts a formatted digest to a Telegram chat.

Env vars required:
    TELEGRAM_BOT_TOKEN   - token from @BotFather
    TELEGRAM_CHAT_ID     - your user id, group id, or channel id (as string, e.g. "-1001234567890")

Optional:
    LOOKBACK_HOURS       - how far back to pull news (default 12)
    KEYWORDS             - comma-separated keywords/tickers to filter on (default: no filter)
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta, timezone

import feedparser
import requests

# ---- Config -----------------------------------------------------------

FEEDS = {
    "Reuters Business":   "https://feeds.reuters.com/reuters/businessNews",
    "MarketWatch Top":    "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "CNBC Markets":       "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "Investing.com News": "https://www.investing.com/rss/news_25.rss",
    "ForexLive":          "https://www.forexlive.com/feed/news",
}

STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_articles.json")
LOOKBACK_HOURS = float(os.environ.get("LOOKBACK_HOURS", "12"))
KEYWORDS = [k.strip().lower() for k in os.environ.get("KEYWORDS", "").split(",") if k.strip()]

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ---- State (dedupe) -----------------------------------------------------

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    # keep the file from growing forever - retain last 2000 hashes
    trimmed = list(seen)[-2000:]
    with open(STATE_FILE, "w") as f:
        json.dump(trimmed, f)


def item_hash(entry):
    key = entry.get("link") or entry.get("title", "")
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ---- Fetch & filter -----------------------------------------------------

def parse_published(entry):
    for field in ("published_parsed", "updated_parsed"):
        val = entry.get(field)
        if val:
            return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
    return None


def matches_keywords(entry):
    if not KEYWORDS:
        return True
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return any(k in text for k in KEYWORDS)


def collect_items(seen):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    grouped = {}

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"[warn] failed to fetch {source}: {e}")
            continue

        fresh = []
        for entry in feed.entries:
            published = parse_published(entry)
            if published and published < cutoff:
                continue
            if not matches_keywords(entry):
                continue
            h = item_hash(entry)
            if h in seen:
                continue
            seen.add(h)
            fresh.append(entry)

        if fresh:
            grouped[source] = fresh

    return grouped


# ---- Format & send -----------------------------------------------------

def format_digest(grouped):
    if not grouped:
        return None

    today = datetime.now().strftime("%A, %d %B %Y")
    lines = [f"*Pre-Market News Digest* — {today}\n"]

    for source, items in grouped.items():
        lines.append(f"*{source}*")
        for entry in items[:8]:  # cap per source so the message stays readable
            title = entry.get("title", "Untitled").replace("*", "").replace("_", "")
            link = entry.get("link", "")
            lines.append(f"• [{title}]({link})")
        lines.append("")  # blank line between sources

    return "\n".join(lines)


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram caps messages at 4096 chars - chunk if needed
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
    seen = load_seen()
    grouped = collect_items(seen)
    digest = format_digest(grouped)

    if digest is None:
        print("No fresh items found in lookback window - nothing sent.")
        return

    send_telegram_message(digest)
    save_seen(seen)
    print("Digest sent.")


if __name__ == "__main__":
    main()
