"""Report ElevenLabs credit burn from the episode log.

Needs no API key. ElevenLabs bills 1 credit per character, and the scheduled
task records the character count of every script it sends, so the log is an
exact record of what the show has spent.

The balance is anchored on a figure read off the ElevenLabs usage page rather
than guessed from a billing date: set REMAINING and AS_OF whenever you check
the site, and every episode logged after that date is subtracted from it.
"""

import re
import sys
from datetime import date
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "docs" / "credit-log.md"

# --- Update these two together, from https://elevenlabs.io/app/usage --------
REMAINING = 96_332
AS_OF = date(2026, 8, 25)
# ---------------------------------------------------------------------------

RENEWS_ON = None          # set to a date once the renewal day is known
EPISODES_PER_MONTH = 21.7  # Sunday to Thursday

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*\|")


def rows():
    if not LOG.exists():
        sys.exit(f"no log at {LOG}")
    for line in LOG.read_text().splitlines():
        match = ROW.match(line.strip())
        if match:
            yield (int(match.group(1)),
                   date.fromisoformat(match.group(2)),
                   int(match.group(3)))


def main() -> None:
    entries = sorted(rows(), key=lambda r: r[1])
    if not entries:
        sys.exit("log has no episodes yet")

    since = [e for e in entries if e[1] > AS_OF]
    spent = sum(chars for _, _, chars in since)
    left = REMAINING - spent
    recent = entries[-5:]
    avg = sum(c for _, _, c in recent) / len(recent)

    print(f"Balance anchored at {REMAINING:,} credits on {AS_OF:%-d %b %Y}\n")
    print(f"  episodes since then : {len(since)}")
    print(f"  spent since then    : {spent:,}")
    print(f"  credits remaining   : {left:,}")
    print(f"  recent average      : {avg:,.0f} characters per episode")

    if avg > 0:
        print(f"  covers about        : {left / avg:.1f} more episodes")

    budget = REMAINING / EPISODES_PER_MONTH
    print(f"\n  sustainable size    : {budget:,.0f} characters "
          f"(~{budget / 900:.1f} min) if this balance must last a month")
    if avg > budget * 1.05:
        print(f"  ⚠ recent episodes run {avg / budget:.1f}x over that")
    elif since:
        print(f"  ✓ recent episodes are within budget")

    if left < avg * 5:
        print(f"\n  ⚠ fewer than 5 episodes of credit left — top up or shorten")

    if RENEWS_ON is None:
        print("\n  Note: renewal date unknown. If the allowance renews monthly,"
              "\n  this balance only has to cover the rest of the cycle and the"
              "\n  sustainable size above is too cautious.")


if __name__ == "__main__":
    main()
