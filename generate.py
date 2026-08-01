"""Daily devotional generator.

Picks one Ellen G. White devotional book at random (seeded by the date, so
every run on the same day picks the same book), fetches today's reading from
whiteestate.org, asks Claude to summarize it into a title + 3 bullets, pick a
fitting hymn from the SDA Hymnal, and write a short takeaway prayer.

Outputs:
  docs/data.json   - consumed by the GitHub Pages site
  message.txt      - Telegram-formatted (HTML) message for the workflow to send
"""

import json
import os
import random
import re
import sys
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

import requests
import anthropic

TIMEZONE = ZoneInfo("Europe/London")
LOCAL_HOUR = 6  # the daily update hour, local time
ROOT = os.path.dirname(os.path.abspath(__file__))
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "A short, fresh title for the day's reading (not just a copy of the original heading)",
        },
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exactly 3 concise bullet points summarizing the devotional's message",
        },
        "hymn_number": {
            "type": "integer",
            "description": "The number of the SDA Hymnal hymn that best accompanies this reading, chosen from the provided list",
        },
        "prayer": {
            "type": "string",
            "description": "A short takeaway prayer (2-3 sentences) flowing from the devotional's theme",
        },
    },
    "required": ["title", "bullets", "hymn_number", "prayer"],
    "additionalProperties": False,
}


def should_run_now() -> bool:
    """On scheduled runs, only proceed when it's LOCAL_HOUR in TIMEZONE.

    The workflow fires at both 05:00 and 06:00 UTC so that exactly one of
    them lands on 6 AM London time year-round (BST vs GMT). Manual runs
    always proceed.
    """
    if os.environ.get("GITHUB_EVENT_NAME") != "schedule":
        return True
    return datetime.now(TIMEZONE).hour == LOCAL_HOUR


def fetch_devotional(slug: str) -> dict:
    url = f"https://whiteestate.org/devotional/{slug}/"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    html = resp.text

    def clean(fragment: str) -> str:
        fragment = re.sub(r"<sup.*?</sup>", "", fragment, flags=re.S)
        fragment = re.sub(r"<[^>]+>", "", fragment)
        return unescape(re.sub(r"\s+", " ", fragment)).strip()

    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    heading = clean(m.group(1)) if m else ""

    verse_m = re.search(
        r'<p class="egw_content_wrapper devotionaltext"[^>]*>(.*?)</p>', html, re.S
    )
    verse = clean(verse_m.group(1)) if verse_m else ""

    paragraphs = [
        clean(p)
        for p in re.findall(
            r'<p class="egw_content_wrapper standard-indented"[^>]*>(.*?)</p>',
            html,
            re.S,
        )
    ]
    paragraphs = [p for p in paragraphs if p]

    if not paragraphs:
        raise RuntimeError(f"No devotional paragraphs found at {url}")

    return {"url": url, "heading": heading, "verse": verse, "paragraphs": paragraphs}


def summarize(book_name: str, devotional: dict, hymns: list) -> dict:
    client = anthropic.Anthropic()
    hymn_list = "\n".join(f'{h["number"]} — {h["title"]} ({h["theme"]})' for h in hymns)
    body = "\n\n".join(devotional["paragraphs"])

    prompt = f"""Here is today's reading from the Ellen G. White devotional book "{book_name}".

Heading: {devotional["heading"]}
Scripture: {devotional["verse"]}

{body}

---

Here is the complete list of hymns in the SDA Hymnal (number — title (theme section)):

{hymn_list}

---

From this devotional, produce:
1. A short, warm title of your own for today's reflection.
2. Exactly 3 bullet points capturing the heart of the message, written simply and devotionally (not academic). Each bullet one sentence.
3. The single hymn from the list above that best matches the reading's theme. Give its number only, and it must be a number from the list.
4. A short takeaway prayer (2-3 sentences, first person) that flows from the reading."""

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> None:
    if not should_run_now():
        print("Not 6 AM in Europe/London; skipping this scheduled run.")
        return

    today = datetime.now(TIMEZONE).date()

    with open(os.path.join(ROOT, "books.json")) as f:
        books = json.load(f)
    with open(os.path.join(ROOT, "hymns.json")) as f:
        hymns = json.load(f)
    hymns_by_number = {h["number"]: h for h in hymns}

    book = random.Random(today.isoformat()).choice(books)
    print(f"Book of the day: {book['name']} ({book['slug']})")

    devotional = fetch_devotional(book["slug"])
    result = summarize(book["name"], devotional, hymns)

    hymn = hymns_by_number.get(result["hymn_number"])
    if hymn is None:
        hymn = {"number": 249, "title": "Praise Him! Praise Him!", "theme": "Jesus Christ"}
    bullets = result["bullets"][:3]

    data = {
        "date": today.isoformat(),
        "date_display": today.strftime("%A, %-d %B %Y"),
        "book": book["name"],
        "source_url": devotional["url"],
        "original_heading": devotional["heading"],
        "verse": devotional["verse"],
        "title": result["title"],
        "bullets": bullets,
        "hymn": {"number": hymn["number"], "title": hymn["title"]},
        "prayer": result["prayer"],
    }

    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "docs", "data.json"), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Wrote docs/data.json")

    bullet_lines = "\n".join(f"• {b}" for b in bullets)
    message = (
        f"🌅 <b>{data['title']}</b>\n"
        f"<i>{data['book']} — {data['date_display']}</i>\n\n"
        f"📖 {data['verse']}\n\n"
        f"{bullet_lines}\n\n"
        f"🎵 Hymn {hymn['number']} — {hymn['title']}\n\n"
        f"🙏 {data['prayer']}\n\n"
        f"<a href=\"{data['source_url']}\">Read the full devotional</a>"
    )
    with open(os.path.join(ROOT, "message.txt"), "w") as f:
        f.write(message)
    print("Wrote message.txt")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
