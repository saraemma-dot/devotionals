# Morning Light — Daily Devotional

Every day at **6 AM (Europe/London)** this project:

1. Picks **one of the 22 Ellen G. White daily devotional books** at random
   (seeded by the date, so the whole day agrees on one book).
2. Fetches **today's reading** from [whiteestate.org](https://whiteestate.org/books/subscribe/).
3. Uses the **Claude API** (`claude-haiku-4-5`) to write:
   - a fresh title,
   - a 3-bullet summary,
   - a matching **SDA Hymnal** hymn (number + title),
   - a short takeaway prayer.
4. Publishes it to the **GitHub Pages site** (`docs/`).
5. Sends the same text to **Telegram**.

## Setup

### 1. GitHub secrets

In the repo: *Settings → Secrets and variables → Actions → New repository secret*.

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | From [console.anthropic.com](https://console.anthropic.com/) → API Keys |
| `TELEGRAM_BOT_TOKEN` | From [@BotFather](https://t.me/BotFather): send `/newbot`, follow the prompts, copy the token |
| `TELEGRAM_CHAT_ID` | Send any message to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id` |

### 2. GitHub Pages

*Settings → Pages → Build and deployment*: Source = **Deploy from a branch**,
Branch = **main**, folder = **/docs**.

### 3. Run it

It runs automatically every morning. To test right now:
*Actions → Daily devotional → Run workflow*.

## Files

| File | Purpose |
|---|---|
| `generate.py` | Fetch + summarize + write outputs |
| `books.json` | The 22 devotional books and their whiteestate.org slugs |
| `hymns.json` | SDA Hymnal (1985): 695 hymns with number, title, theme |
| `docs/index.html` | The website |
| `docs/data.json` | Today's generated devotional (updated daily) |
| `.github/workflows/daily.yml` | The 6 AM automation |

## Notes

- The workflow fires at 05:00 **and** 06:00 UTC; the script only proceeds on
  whichever run is 6 AM London time, so daylight saving is handled.
- Hymn **lyrics are never reproduced** (many are copyrighted) — only the hymn
  number and title are referenced.
- Devotional text © Ellen G. White Estate; only a short summary is published,
  with a link to the full reading.
