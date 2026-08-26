"""Render episode.json to a single MP3 with ElevenLabs.

Each line is rendered separately so the two hosts keep their own voices, then
the pieces are joined with a short pause between turns. Voice ids and the
model are looked up by name at runtime rather than hard-coded, so a renamed
voice or a new model version does not silently break the show.

Needs ELEVENLABS_API_KEY.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EPISODE = REPO / "episode.json"
INCOMING = REPO / "incoming"
ASSETS = REPO / "assets"
WORK = REPO / ".render"
CROSSFADE = 1.5   # seconds of overlap between music and speech

API = "https://api.elevenlabs.io/v1"
# Explicit voice ids, chosen by ear. Names in the library are ambiguous
# (there is more than one "Eric"), so the id is the source of truth.
VOICES = {
    "DANA": "uYXf8XasLslADfZ2MB4u",   # Hope
    "ADAM": "uHu0tu8NXvFWhmnFp4ZR",   # Eric
}
MODEL_PREFERENCE = ["eleven_v3", "eleven_multilingual_v2", "eleven_turbo_v2_5"]
BITRATE = "96k"

# Text-to-dialogue renders a whole exchange in one pass, so the speakers react
# to each other instead of each line being performed in isolation. The endpoint
# is reliable up to about 2,000 characters, so long episodes go in chunks split
# on speaker boundaries.
DIALOGUE_CHARS = 1800
# Lower stability = more expressive. ElevenLabs calls ~0.5 "Natural" and the
# lower end "Creative"; conversation wants the expressive end.
STABILITY = float(os.environ.get("FINTECH_STABILITY", "0.35"))


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
    """Confirm each configured voice id resolves, and report its real name."""
    for speaker, voice_id in VOICES.items():
        try:
            name = api_get(f"voices/{voice_id}", key).get("name", "?")
        except urllib.error.HTTPError as exc:
            sys.exit(f"voice id {voice_id} for {speaker} is not reachable "
                     f"(HTTP {exc.code}). Check the id and the key's Voices "
                     f"permission.")
        print(f"  {speaker} -> {name} ({voice_id})")
    return dict(VOICES)


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
    """Single line, one voice. Used by the audition page."""
    body = json.dumps({
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": STABILITY, "similarity_boost": 0.8},
    }).encode()
    request = urllib.request.Request(
        f"{API}/text-to-speech/{voice_id}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.write_bytes(response.read())


def chunk_lines(lines, voices):
    """Group consecutive lines into blocks the dialogue endpoint can take."""
    blocks, current, size = [], [], 0
    for line in lines:
        speaker = line["speaker"].upper()
        if speaker not in voices:
            print(f"  ! unknown speaker {speaker!r}, skipping the line")
            continue
        text = line["text"].strip()
        if not text:
            continue
        if current and size + len(text) > DIALOGUE_CHARS:
            blocks.append(current)
            current, size = [], 0
        current.append({"text": text, "voice_id": voices[speaker]})
        size += len(text)
    if current:
        blocks.append(current)
    return blocks


def speak_dialogue(inputs, model: str, key: str, dest: Path) -> None:
    """A whole exchange in one pass, so the voices respond to each other."""
    body = json.dumps({
        "inputs": inputs,
        "model_id": model,
        "settings": {"stability": STABILITY},
    }).encode()
    request = urllib.request.Request(
        f"{API}/text-to-dialogue", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=300) as response:
        dest.write_bytes(response.read())


def dress(body: Path, out: Path) -> None:
    """Top and tail the episode with the theme music, crossfaded.

    A hard cut from music into speech sounds amateur; overlapping them by a
    second and a half is what makes it sound produced.
    """
    parts = [p for p in (ASSETS / "intro.mp3", body, ASSETS / "outro.mp3")
             if p.exists()]

    if len(parts) == 1:
        shutil.copy(body, out)
        print("  no music in assets/ — published without a theme")
        return

    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for part in parts:
        args += ["-i", str(part)]

    filters, label = [], "[0:a]"
    for position in range(1, len(parts)):
        nxt = f"[x{position}]"
        filters.append(
            f"{label}[{position}:a]acrossfade=d={CROSSFADE}:c1=tri:c2=tri{nxt}")
        label = nxt

    args += ["-filter_complex", ";".join(filters), "-map", label,
             "-c:a", "libmp3lame", "-b:a", BITRATE, str(out)]
    subprocess.run(args, check=True)
    print(f"  music: {' + '.join(part.stem for part in parts)}")


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

    blocks = chunk_lines(lines, voices)
    print(f"  {len(blocks)} dialogue block(s)")

    pieces = []
    for index, inputs in enumerate(blocks):
        part = WORK / f"{index:03d}.mp3"
        try:
            speak_dialogue(inputs, model, key, part)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            sys.exit(f"ElevenLabs error {exc.code} on block {index}: {detail}")
        pieces.append(part)
        print(f"  block {index + 1}/{len(blocks)} "
              f"({len(inputs)} turns, {sum(len(i['text']) for i in inputs):,} chars)",
              flush=True)

    if not pieces:
        sys.exit("nothing was rendered")

    listing = WORK / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in pieces))

    body = WORK / "body.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c:a", "libmp3lame", "-b:a", BITRATE,
         str(body.resolve())],
        check=True, cwd=WORK)

    INCOMING.mkdir(exist_ok=True)
    out = INCOMING / f"Fintech Pulse Daily Ep. {episode['number']:02d}.mp3"
    dress(body, out)

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
