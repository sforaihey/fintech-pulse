"""Collect new episode MP3s from the Notion drop page.

The claude.ai scheduled task cannot write to GitHub -- there is no GitHub
connector -- so it uploads the finished episode to a Notion page instead.
This script is the other half: it reads that page, downloads any episode the
feed does not already have, and drops it into incoming/ for build_feed.py.

Needs NOTION_TOKEN in the environment. Nothing else is secret: the page id is
not sensitive, and the file URLs Notion returns are short-lived signed links.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INCOMING = REPO / "incoming"
META = REPO / "episodes.json"

PAGE_ID = "3c7e7f30-e119-81ad-be17-d45defeeee80"
NOTION_VERSION = "2022-06-28"
EP_PATTERN = re.compile(r"(?:episode|ep)[\s._-]*(\d+)", re.IGNORECASE)


def api(path: str, token: str) -> dict:
    request = urllib.request.Request(
        f"https://api.notion.com/v1/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def episode_files(token: str):
    """Yield (episode_number, filename, signed_url) for files on the page."""
    cursor = None
    while True:
        path = f"blocks/{PAGE_ID}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        payload = api(path, token)

        for block in payload.get("results", []):
            if block.get("type") != "file":
                continue
            entry = block["file"]
            name = entry.get("name") or ""
            url = entry.get("file", {}).get("url") or entry.get(
                "external", {}).get("url")
            match = EP_PATTERN.search(name)
            if not url or not match:
                continue
            yield int(match.group(1)), name, url

        if not payload.get("has_more"):
            return
        cursor = payload.get("next_cursor")


def already_published() -> set[int]:
    if not META.exists():
        return set()
    return {int(k) for k in json.loads(META.read_text())}


def main() -> None:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        sys.exit("NOTION_TOKEN is not set — nothing can be collected.")

    INCOMING.mkdir(exist_ok=True)
    have = already_published()
    collected = 0

    try:
        files = list(episode_files(token))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        sys.exit(f"Notion API error {exc.code}: {detail}\n"
                 f"Is the drop page shared with the integration?")

    if not files:
        print("no episode files on the drop page")
        return

    for number, name, url in sorted(files):
        if number in have:
            print(f"  ep {number:02d} already in the feed, skipping")
            continue
        dest = INCOMING / f"Fintech Pulse Daily Ep. {number:02d}.mp3"
        print(f"  downloading ep {number:02d} from {name}")
        urllib.request.urlretrieve(url, dest)
        size = dest.stat().st_size
        if size < 100_000:
            dest.unlink()
            print(f"  ! ep {number:02d} was only {size} bytes — discarded")
            continue
        print(f"    saved {dest.name} ({size/1e6:.1f} MB)")
        collected += 1

    print(f"collected {collected} new episode(s)")


if __name__ == "__main__":
    main()
