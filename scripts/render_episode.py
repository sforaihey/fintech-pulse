"""Render episode.json to a single MP3 with ElevenLabs.

Each line is rendered separately so the two hosts keep their own voices, then
the pieces are joined with a short pause between turns. Voice ids and the
model are looked up by name at runtime rather than hard-coded, so a renamed
voice or a new model version does not silently break the show.

Needs ELEVENLABS_API_KEY.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EPISODE = REPO / "episode.json"
INCOMING = REPO / "incoming"
WORK = REPO / ".render"

API = "https://api.elevenlabs.io/v1"
VOICES = {"DANA": "Matilda", "ADAM": "Eric"}
MODEL_PREFERENCE = ["eleven_v3", "eleven_multilingual_v2", "eleven_turbo_v2_5"]
GAP_SECONDS = 0.28
BITRATE = "96k"


def api_get(path: str, key: str):
    request = urllib.request.Request(f"{API}/{path}", headers={"xi-api-key": key})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def match_voice(wanted: str, catalogue: dict) -> str | None:
    """Find a voice by name, tolerating the descriptive suffix ElevenLabs adds.

    The library stores them as "lauren - conversational ai", so an exact
    match on "Lauren" finds nothing.
    """
    wanted = wanted.strip().lower()
    for name, voice_id in catalogue.items():
        if name == wanted or name.split(" - ")[0].strip() == wanted:
            return voice_id
    return None


def resolve_voices(key: str) -> dict:
    catalogue = {v["name"].strip().lower(): v["voice_id"]
                 for v in api_get("voices", key).get("voices", [])}
    resolved = {}
    for speaker, wanted in VOICES.items():
        voice_id = match_voice(wanted, catalogue)
        if not voice_id:
            sys.exit(f"voice '{wanted}' not found. "
                     f"Library holds: {', '.join(sorted(catalogue))}")
        resolved[speaker] = voice_id
        print(f"  {speaker} -> {wanted} ({voice_id})")
    return resolved


def resolve_model(key: str) -> str:
    try:
        available = {m["model_id"] for m in api_get("models", key)}
    except Exception as exc:                     # noqa: BLE001
        print(f"  could not list models ({exc}); using {MODEL_PREFERENCE[0]}")
        return MODEL_PREFERENCE[0]
    for candidate in MODEL_PREFERENCE:
        if candidate in available:
            print(f"  model -> {candidate}")
            return candidate
    sys.exit(f"none of {MODEL_PREFERENCE} available; account has: {available}")


def speak(text: str, voice_id: str, model: str, key: str, dest: Path) -> None:
    body = json.dumps({
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8},
    }).encode()
    request = urllib.request.Request(
        f"{API}/text-to-speech/{voice_id}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.write_bytes(response.read())


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    if not EPISODE.exists():
        print("no episode.json — nothing to render")
        return

    episode = json.loads(EPISODE.read_text())
    lines = episode["lines"]
    print(f"rendering episode {episode['number']:02d}: {len(lines)} lines, "
          f"{episode['characters']:,} characters")

    WORK.mkdir(exist_ok=True)
    for stale in WORK.iterdir():
        stale.unlink()

    voices = resolve_voices(key)
    model = resolve_model(key)

    silence = WORK / "gap.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=mono", "-t", str(GAP_SECONDS),
         "-b:a", BITRATE, str(silence)], check=True)

    pieces = []
    for index, line in enumerate(lines):
        speaker = line["speaker"].upper()
        if speaker not in voices:
            print(f"  ! unknown speaker {speaker!r} on line {index}, skipping")
            continue
        part = WORK / f"{index:03d}.mp3"
        try:
            speak(line["text"], voices[speaker], model, key, part)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            sys.exit(f"ElevenLabs error {exc.code} on line {index}: {detail}")
        pieces += [part, silence]
        print(f"  line {index + 1}/{len(lines)} ({speaker})", flush=True)

    if not pieces:
        sys.exit("nothing was rendered")

    listing = WORK / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in pieces[:-1]))

    INCOMING.mkdir(exist_ok=True)
    out = INCOMING / f"Fintech Pulse Daily Ep. {episode['number']:02d}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c:a", "libmp3lame", "-b:a", BITRATE,
         str(out.resolve())],
        check=True, cwd=WORK)

    seconds = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True).stdout)
    print(f"  wrote {out.name} — {int(seconds)//60}:{int(seconds)%60:02d}, "
          f"{out.stat().st_size/1e6:.1f} MB")

    for leftover in WORK.iterdir():
        leftover.unlink()
    WORK.rmdir()


if __name__ == "__main__":
    main()
