"""Generate the show's intro and outro music. Run once, reuse forever.

The files land in assets/ and are committed, so every episode is topped and
tailed with them at no further cost. Re-run only to change the sound.

Needs ELEVENLABS_API_KEY with the Music Generation permission.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
API = "https://api.elevenlabs.io/v1/music"

PIECES = {
    "intro": {
        "ms": 11000,
        "prompt": (
            "Short broadcast news theme for a daily financial markets podcast. "
            "Confident and modern, not dramatic. A clean synth pulse with a "
            "muted piano motif over a soft four-on-the-floor kick, subtle "
            "rising strings. Sophisticated and understated, the sound of a "
            "serious business briefing. Resolves cleanly at the end, ready for "
            "a presenter to speak over the tail. No vocals."),
    },
    "outro": {
        "ms": 7000,
        "prompt": (
            "Closing sting for a daily financial news podcast, matching a calm "
            "modern broadcast theme. The same muted piano motif resolving down "
            "over a soft synth pad, warm and settled, fading gently to silence. "
            "No vocals, no drums."),
    },
}


def compose(name: str, spec: dict, key: str) -> Path:
    body = json.dumps({
        "prompt": spec["prompt"],
        "music_length_ms": spec["ms"],
        "model_id": "music_v2",
    }).encode()
    request = urllib.request.Request(
        API, data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=300) as response:
        audio = response.read()

    ASSETS.mkdir(exist_ok=True)
    dest = ASSETS / f"{name}.mp3"
    dest.write_bytes(audio)
    print(f"  {name}: {spec['ms'] / 1000:.0f}s, {len(audio) / 1e6:.1f} MB "
          f"-> {dest.relative_to(ASSETS.parent)}")
    return dest


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")

    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, spec in PIECES.items():
        if only and name != only:
            continue
        try:
            compose(name, spec, key)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code in (401, 403):
                sys.exit(f"HTTP {exc.code}: the API key needs the "
                         f"'Music Generation' permission.\n{detail}")
            sys.exit(f"HTTP {exc.code}: {detail}")

    print("\nDone. Commit assets/ — episodes use these from now on.")


if __name__ == "__main__":
    main()
