"""Report ElevenLabs credit burn and what it means for episode length.

Two ways of knowing the balance:

  * Live -- if ELEVENLABS_API_KEY is set, GET /v1/user/subscription gives the
    exact character_count, character_limit and reset date. Nothing to maintain.
  * Manual -- otherwise fall back to a figure read off the usage page. Update
    REMAINING and AS_OF together whenever you check the site.

Either way the per-episode budget is derived from the publishing days actually
left in the billing cycle, counting Sunday to Thursday only.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "docs" / "credit-log.md"
API = "https://api.elevenlabs.io/v1/user/subscription"
RIYADH = timezone(timedelta(hours=3))

# --- Fallback only, used when no API key is set. From the usage page. -------
REMAINING = 96_332
ALLOWANCE = 130_230
AS_OF = date(2026, 8, 25)
RESET_DAY = 25
# ---------------------------------------------------------------------------

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*\|")


def rows():
    if not LOG.exists():
        return
    for line in LOG.read_text().splitlines():
        match = ROW.match(line.strip())
        if match:
            yield (int(match.group(1)),
                   date.fromisoformat(match.group(2)),
                   int(match.group(3)))


def live_balance(key: str):
    """(remaining, allowance, reset date, tier) straight from ElevenLabs."""
    request = urllib.request.Request(API, headers={"xi-api-key": key})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read())
    used, limit = data["character_count"], data["character_limit"]
    reset = datetime.fromtimestamp(
        data["next_character_count_reset_unix"], RIYADH).date()
    return limit - used, limit, reset, data.get("tier", "?")


def fallback_reset(today: date) -> date:
    month, year = today.month, today.year
    if today.day >= RESET_DAY:
        month, year = (1, year + 1) if month == 12 else (month + 1, year)
    return date(year, month, RESET_DAY)


def publishing_days(start: date, end: date) -> int:
    """Sunday-to-Thursday days in [start, end)."""
    count, day = 0, start
    while day < end:
        if day.weekday() not in (4, 5):
            count += 1
        day += timedelta(days=1)
    return count


def main() -> None:
    today = datetime.now(RIYADH).date()
    key = os.environ.get("ELEVENLABS_API_KEY")

    if key:
        try:
            remaining, allowance, reset, tier = live_balance(key)
            source = f"live from ElevenLabs ({tier} plan)"
        except urllib.error.HTTPError as exc:
            sys.exit(f"ElevenLabs API error {exc.code} — check ELEVENLABS_API_KEY")
        except (urllib.error.URLError, KeyError) as exc:
            sys.exit(f"could not read the live balance: {exc}")
    else:
        remaining, allowance = REMAINING, ALLOWANCE
        reset = fallback_reset(today)
        source = f"manual figure from {AS_OF:%-d %b}"
        for _, when, chars in rows():
            if when > AS_OF:
                remaining -= chars

    left = publishing_days(today + timedelta(days=1), reset)
    budget = remaining / left if left else 0

    print(f"Credits — {source}\n")
    print(f"  remaining        : {remaining:,} of {allowance:,}")
    print(f"  cycle renews     : {reset:%-d %b %Y}")
    print(f"  episodes to cover: {left} (Sun-Thu)")
    print(f"  budget each      : {budget:,.0f} characters "
          f"(~{budget / 900:.1f} min)")

    recent = sorted(rows(), key=lambda r: r[1])[-5:]
    if recent:
        avg = sum(c for _, _, c in recent) / len(recent)
        print(f"\n  recent average   : {avg:,.0f} characters per episode")
        if budget and avg > budget * 1.05:
            print(f"  ⚠ running {avg / budget:.1f}x over — episodes too long")
        elif budget:
            print(f"  ✓ within budget ({avg / budget:.0%} of the allowance)")
        if avg and remaining < avg * 5:
            print("  ⚠ under 5 episodes of credit left — top up or shorten")

    if not key:
        print("\n  Set ELEVENLABS_API_KEY for a live balance instead of this"
              "\n  hand-maintained figure. See docs/delivery.md.")


if __name__ == "__main__":
    main()
