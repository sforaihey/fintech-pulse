"""Generate the show's intro and outro music. Run once, reuse forever.

The files land in assets/ and are committed, so every episode is topped and
tailed with them at no further cost. Re-run only to change the sound.

Needs ELEVENLABS_API_KEY with the Music Generation permission.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
API = "https://api.elevenlabs.io/v1/music"

# The show ident: a voice over the top of the opening music, so the intro is
# not a bare instrumental. Spoken by Dana, for continuity with the show.
IDENT_TEXT = os.environ.get("FINTECH_IDENT", "Fintech Pulse Daily.")
IDENT_VOICE = "OZxMHsGaBmV5pjMIDIn0"
IDENT_DELAY_MS = 2200   # let the music establish before the voice lands
MUSIC_UNDER = 0.62      # music level while the voice is over it

PIECES = {
    "intro-music": {
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


def build_ident(key: str) -> None:
    """Speak the show name over the opening music."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from render_episode import resolve_model, speak

    voice = ASSETS / "ident-vo.mp3"
    speak(IDENT_TEXT, IDENT_VOICE, resolve_model(key), key, voice)
    print(f"  ident: \"{IDENT_TEXT}\"")

    music, out = ASSETS / "intro-music.mp3", ASSETS / "intro.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(music), "-i", str(voice),
         "-filter_complex",
         f"[0:a]volume={MUSIC_UNDER}[m];"
         f"[1:a]adelay={IDENT_DELAY_MS}|{IDENT_DELAY_MS},volume=1.35[v];"
         # amix halves levels unless told not to; the 1.4 restores the bed
         # to roughly its original loudness with headroom to spare.
         f"[m][v]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
         f"volume=1.4[a]",
         "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
        check=True)
    print(f"  intro: music + voice -> {out.relative_to(ASSETS.parent)}")


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")

    for name, spec in PIECES.items():
        if (ASSETS / f"{name}.mp3").exists() and "--force" not in sys.argv:
            print(f"  {name}: already present, keeping it (--force to replace)")
            continue
        try:
            compose(name, spec, key)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code in (401, 403):
                sys.exit(f"HTTP {exc.code}: the API key needs the "
                         f"'Music Generation' permission.\n{detail}")
            sys.exit(f"HTTP {exc.code}: {detail}")

    build_ident(key)
    print("\nDone. Commit assets/ — episodes use these from now on.")


if __name__ == "__main__":
    main()
