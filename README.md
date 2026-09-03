# Pre-Market News & Calendar → Telegram

Two scripts, one Telegram bot:

1. **`news_to_telegram.py`** - headlines from financial RSS feeds.
2. **`economic_calendar_to_telegram.py`** - today's Medium/High impact
   economic events, pulled from the same Forex Factory feed that powers
   FTMO's own economic calendar widget.

Both run on a schedule (default: weekday mornings before market open) for
free on GitHub Actions - no server needed.

## 1. Create the Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts.
2. Copy the token it gives you (looks like `123456:ABC-...`). This is `TELEGRAM_BOT_TOKEN`.
3. Decide where the digest should land:
   - **DM to yourself**: message your new bot once (anything), then visit
     `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and read
     `message.chat.id` from the JSON. That's your `TELEGRAM_CHAT_ID`.
   - **A group**: add the bot to the group, send a message, then use the same
     `getUpdates` trick - group IDs are negative numbers.
   - **A channel**: add the bot as admin, post something, same trick - channel
     IDs usually look like `-100xxxxxxxxxx`.

## 2. Test it locally (optional but recommended)

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-chat-id"
python news_to_telegram.py
```

You should get a message in Telegram within a few seconds.

## 3. Deploy the schedule (GitHub Actions - free)

1. Push this folder to a **private** GitHub repo (private is fine, Actions
   still works, and it keeps your setup out of public view).
2. In the repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Add `TELEGRAM_BOT_TOKEN`
   - Add `TELEGRAM_CHAT_ID`
3. The workflow at `.github/workflows/schedule.yml` is already set to run
   weekdays at 05:45 UTC. Adjust the `cron:` line for your desired local
   pre-market time (GitHub cron is always in UTC, and doesn't auto-adjust
   for daylight saving - you may want to nudge it twice a year).
4. Go to the **Actions** tab → select the workflow → **Run workflow** to
   trigger it manually and confirm it works end to end before trusting the
   schedule.

## About the economic calendar source

FTMO's calendar page (`ftmo.com/en/calendar`) is a JavaScript app, so there's
no static data to scrape from it directly - and per FTMO Academy's own
material, it sources its events from **Forex Factory** anyway. Forex Factory
publishes a free weekly JSON feed at
`https://nfs.faireconomy.media/ff_calendar_thisweek.json` that's widely used
by MT4/MT5 news indicators, so the script reads from there instead: same
underlying data, no scraping fragility. Forex Factory rate-limits this feed
to a couple of requests per 5 minutes, which a once-daily run is nowhere
near.

The script converts every event's time into `CALENDAR_TIMEZONE` (default
`Europe/Helsinki`, matching your original FTMO link) and keeps only events
happening "today" in that timezone with impact Medium or High.

## Customizing

- **Feeds**: edit the `FEEDS` dict in `news_to_telegram.py`. Any RSS/Atom URL
  works - add or remove sources freely (forex-specific, crypto, a particular
  exchange's press releases, etc.).
- **Keyword/ticker filter**: set the `KEYWORDS` env var (comma-separated,
  e.g. `EUR/USD,fed,ecb,inflation`) to only include items mentioning those
  terms. Leave empty to get everything.
- **Lookback window**: `LOOKBACK_HOURS` controls how far back it looks each
  run (default 14h, tuned for a once-daily morning run).
- **Dedupe**: `seen_articles.json` tracks what's already been sent so reruns
  don't repeat headlines; the GitHub Actions job commits this file back to
  the repo after each run so state persists between runs.
- **Calendar impact filter**: `MIN_IMPACT` env var - `"medium"` (default)
  includes both Medium and High; set to `"high"` for High-only.
- **Calendar timezone**: `CALENDAR_TIMEZONE` env var, any IANA name (e.g.
  `"Europe/Helsinki"`, `"America/New_York"`).

## Natural next steps (if you want to keep vibe-coding this)

- Add a sentiment/summary pass: send each headline through the Claude or
  OpenAI API before posting, to get a one-line "why this matters" under
  each link.
- Split into multiple digests (e.g. macro vs. your specific watchlist)
  sent to different Telegram topics/threads.
- Swap RSS for a paid news API (Benzinga, NewsAPI, Polygon.io) once you know
  what's actually useful to you - RSS is the free way to prove the workflow
  first.
