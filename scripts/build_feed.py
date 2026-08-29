"""Tag episode MP3s and build the podcast RSS feed.

Reads new episodes out of the Desktop folder, writes ID3 tags and embedded
cover art, copies them into episodes/, then regenerates feed.xml.

Episode dates live in episodes.json so they stay stable across rebuilds --
file mtimes change whenever a file is copied, and Apple Podcasts orders the
show by pubDate, so the dates must not drift.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
# NOT ~/Desktop: macOS TCC blocks launchd jobs from reading it, and the
# job hangs on a consent prompt that can never be shown. The Desktop
# 'Fintech podcast' folder is a symlink to this path. CI overrides it.
SOURCE = Path(os.environ.get("FINTECH_SOURCE",
                             Path.home() / "fintech-pulse-incoming"))
EPISODES = REPO / "episodes"
META = REPO / "episodes.json"
COVER = REPO / "cover.jpg"

BASE_URL = "https://sforaihey.github.io/fintech-pulse"
RIYADH = timezone(timedelta(hours=3))
PUBLISH_HOUR = 7   # the cloud task runs ~07:30 Riyadh
KEEP_LAST = 40    # rolling window of episodes kept in the feed
ADOPT = os.environ.get("FINTECH_ADOPT") == "1"  # CI consumes incoming/
DEFAULT_SUMMARY = "أخبار الفنتك السعودية والعالمية، وشرح منتج."

SHOW = {
    "title": "فنتك بلس",
    "author": "Sawsan Alforaihey",
    "email": "s.foraihey@gmail.com",
    "description": (
        "نشرة يومية قصيرة عن المدفوعات والبنوك والفنتك — وش صار، وليه يهم، "
        "ووش يعني للسوق السعودي والخليجي. وفي كل حلقة شرح لمنتج فنتك واحد "
        "بلغة واضحة. مذيعان، عشر دقايق، جاهزة قبل طريق الدوام."
    ),
    "language": "ar",
    "category": "Business",
    "subcategory": "Investing",
}

# Tolerant of however the download happens to be named: "ep03",
# "Ep. 03", "episode 3", "Fintech Pulse Daily Ep 3" all resolve.
EP_PATTERN = re.compile(r"(?:episode|ep)[\s._-]*(\d+)", re.IGNORECASE)


def episode_number(path: Path) -> int | None:
    match = EP_PATTERN.search(path.stem)
    return int(match.group(1)) if match else None


def duration_seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def hms(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def load_meta() -> dict:
    return json.loads(META.read_text()) if META.exists() else {}


def tag_episode(src: Path, dest: Path, entry: dict, number: int) -> None:
    """Write ID3 tags and embed the cover, so car players show it properly."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(src), "-i", str(COVER),
         "-map", "0:a", "-map", "1:v",
         "-c:a", "copy", "-c:v", "mjpeg", "-disposition:v", "attached_pic",
         "-id3v2_version", "3",
         "-metadata", f"title={entry['title']}",
         "-metadata", f"artist={SHOW['author']}",
         "-metadata", f"album={SHOW['title']}",
         "-metadata", f"track={number}",
         "-metadata", f"date={entry['date'][:4]}",
         "-metadata", "genre=Podcast",
         "-metadata", f"comment={entry['summary']}",
         str(dest)],
        check=True,
    )


def working_days_back(anchor: datetime, count: int) -> datetime:
    """Step back `count` publishing days, skipping Friday and Saturday."""
    day = anchor
    while count > 0:
        day -= timedelta(days=1)
        if day.weekday() not in (4, 5):  # Fri, Sat off
            count -= 1
    return day


def sync_episodes() -> dict:
    """Bring the repo's episodes into line with whatever the source holds.

    Two modes. Locally the drop folder is the source of truth and is only
    read, so deleting a file there removes the episode from the feed. In
    ADOPT mode (CI) the incoming files are *consumed* -- tagged into
    episodes/ and deleted -- because the uploader only ever adds one file
    and episodes.json is what carries the show forward.
    """
    meta = load_meta()
    EPISODES.mkdir(exist_ok=True)

    sources = []
    for src in sorted(SOURCE.glob("*.mp3")):
        number = episode_number(src)
        if number is None:
            print(f"  skip (no episode number): {src.name}")
            continue
        sources.append((number, src))
    sources.sort(reverse=True)

    today = datetime.now(RIYADH).replace(
        hour=PUBLISH_HOUR, minute=30, second=0, microsecond=0)

    if ADOPT:
        for number, src in sources:
            key = f"{number:02d}"
            name = src.name
            if key not in meta:
                meta[key] = {
                    "title": f"Ep. {key} - {today:%-d %b %Y}",
                    "date": today.isoformat(),
                    "summary": DEFAULT_SUMMARY,
                }
                print(f"  adopted episode {key} -> {meta[key]['title']}")
            tag_episode(src, EPISODES / f"fintech-pulse-ep{key}.mp3",
                        meta[key], number)
            src.unlink()
            print(f"  tagged episode {key}, consumed {name}")
    else:
        # Anything no longer backed by a source file leaves the feed, so the
        # published show always matches the drop folder.
        live = {f"{number:02d}" for number, _ in sources[:KEEP_LAST]}
        for key in sorted(set(meta) - live):
            meta.pop(key, None)
            print(f"  removed episode {key} (no source file)")

        newest = max((number for number, _ in sources), default=0)
        for number, src in sources[:KEEP_LAST]:
            key = f"{number:02d}"
            dest = EPISODES / f"fintech-pulse-ep{key}.mp3"
            if key not in meta:
                published = working_days_back(today, newest - number)
                meta[key] = {
                    "title": f"Ep. {key} - {published:%-d %b %Y}",
                    "date": published.isoformat(),
                    "summary": DEFAULT_SUMMARY,
                }
                print(f"  new episode {key} -> {meta[key]['title']}")
            if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
                tag_episode(src, dest, meta[key], number)
                print(f"  tagged {dest.name}")

    # Rolling window, then drop anything with no audio behind it and refresh
    # the numbers the feed quotes.
    for key in sorted(meta, key=int, reverse=True)[KEEP_LAST:]:
        meta.pop(key, None)
        print(f"  pruned episode {key} (outside newest {KEEP_LAST})")

    for key in sorted(meta, key=int):
        dest = EPISODES / f"fintech-pulse-ep{key}.mp3"
        if not dest.exists():
            meta.pop(key, None)
            continue
        meta[key]["duration"] = round(duration_seconds(dest))  # whole seconds: avoids CI/local churn
        meta[key]["bytes"] = dest.stat().st_size
        meta[key]["file"] = dest.name

    for stale in EPISODES.glob("*.mp3"):
        if (episode_number(stale) is None
                or f"{episode_number(stale):02d}" not in meta):
            stale.unlink()
            print(f"  deleted orphaned {stale.name}")

    META.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    return meta



def build_feed(meta: dict) -> str:
    items = []
    for key in sorted(meta, key=int, reverse=True):
        e = meta[key]
        if "file" not in e:
            continue
        published = datetime.fromisoformat(e["date"])
        url = f"{BASE_URL}/episodes/{e['file']}"
        items.append(f"""    <item>
      <title>{escape(e['title'])}</title>
      <description>{escape(e['summary'])}</description>
      <itunes:summary>{escape(e['summary'])}</itunes:summary>
      <content:encoded><![CDATA[{e.get('notes', '') or e['summary']}]]></content:encoded>
      <pubDate>{published.strftime('%a, %d %b %Y %H:%M:%S %z')}</pubDate>
      <enclosure url="{url}" length="{e['bytes']}" type="audio/mpeg"/>
      <guid isPermaLink="false">fintech-pulse-ep{key}</guid>
      <itunes:duration>{hms(e['duration'])}</itunes:duration>
      <itunes:episode>{int(key)}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>false</itunes:explicit>
    </item>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:atom="http://www.w3.org/2005/Atom"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(SHOW['title'])}</title>
    <link>{BASE_URL}/</link>
    <atom:link href="{BASE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <language>{SHOW['language']}</language>
    <description>{escape(SHOW['description'])}</description>
    <itunes:summary>{escape(SHOW['description'])}</itunes:summary>
    <itunes:author>{escape(SHOW['author'])}</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{BASE_URL}/cover.jpg"/>
    <image>
      <url>{BASE_URL}/cover.jpg</url>
      <title>{escape(SHOW['title'])}</title>
      <link>{BASE_URL}/</link>
    </image>
    <itunes:owner>
      <itunes:name>{escape(SHOW['author'])}</itunes:name>
      <itunes:email>{SHOW['email']}</itunes:email>
    </itunes:owner>
    <itunes:category text="{SHOW['category']}">
      <itunes:category text="{SHOW['subcategory']}"/>
    </itunes:category>
{chr(10).join(items)}
  </channel>
</rss>
"""


if __name__ == "__main__":
    if not SOURCE.exists():
        sys.exit(f"source folder not found: {SOURCE}")

    print(f"reading {SOURCE}")
    meta = sync_episodes()
    (REPO / "feed.xml").write_text(build_feed(meta))
    print(f"wrote feed.xml with {len(meta)} episode(s)")
