"""Render episode.json to a single MP3 with ElevenLabs.

Render conversational blocks with explicit voice IDs. Keep content-addressed
audio blocks for selective repair; never silently omit a speaker or publish
an episode outside the ten-minute duration range.

Needs ELEVENLABS_API_KEY.
"""

import json
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from episode_quality import validate_lines, validate_duration

REPO = Path(__file__).resolve().parent.parent
EPISODE = Path(os.environ.get("FINTECH_SCRIPT", str(REPO / "episode.json")))
INCOMING = Path(os.environ.get("FINTECH_OUTPUT", str(REPO / "incoming")))
ASSETS = REPO / "assets"
WORK = REPO / ".render"
# The music fades; the speech never does. acrossfade would fade BOTH sides,
# which buries the first words of the episode under the intro.
INTRO_FADE = 2.0     # music fades out over this long
INTRO_OVERLAP = -0.15  # a clean gap after the ident/music, never mask first words
OUTRO_OVERLAP = -0.15  # do not mask the final word either
OUTRO_FADE_IN = 0.8

API = "https://api.elevenlabs.io/v1"
# Explicit voice ids, chosen by ear. Names in the library are ambiguous
# (there is more than one "Eric"), so the id is the source of truth.
VOICES = {
    "سلطان": "rUaPbzcZIu8df8iNL9WZ",
    "فيصل": "wyC6KvCMTAXGbiCKlfSx",
}
# Declaring the language stops the model guessing from Latin-script technical
# terms embedded in Arabic sentences.
LANGUAGE = os.environ.get("FINTECH_LANGUAGE", "ar")
MODEL_PREFERENCE = ["eleven_v3"]
BITRATE = "96k"

# Text-to-dialogue renders a whole exchange in one pass, so the speakers react
# to each other instead of each line being performed in isolation. The endpoint
# is reliable up to about 2,000 characters, so long episodes go in chunks split
# on speaker boundaries.
DIALOGUE_CHARS = int(os.environ.get('FINTECH_BLOCK_CHARS', '1800'))
if not 400 <= DIALOGUE_CHARS <= 2000:
    raise ValueError('Dialogue block size must be between 400 and 2000 characters')
# Natural, rather than Creative: expression belongs mainly in the writing.
# This is a risk reduction, NOT a guarantee of regional accent consistency.
STABILITY = float(os.environ.get("FINTECH_STABILITY", "0.5"))
SEED = int(os.environ.get("FINTECH_SEED", "31"))
ACCENT_CUE = "[strong Saudi accent] "


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
            print(f"  {speaker} -> {name} ({voice_id})")
        except urllib.error.HTTPError as exc:
            # Premade voices synthesise fine without being in the library, so
            # a failed lookup is not a reason to abandon a written episode.
            print(f"  {speaker} -> {voice_id} (not in library, HTTP "
                  f"{exc.code} — will still try to synthesise)")
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


def speak(text: str, voice_id: str, model: str, key: str, dest: Path,
          language: str | None = None) -> None:
    """Single line, one voice. Used by the audition page."""
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": STABILITY, "similarity_boost": 0.8},
    }
    if language:
        payload["language_code"] = language
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{API}/text-to-speech/{voice_id}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.write_bytes(response.read())


def chunk_lines(lines, voices):
    """Group consecutive lines into blocks the dialogue endpoint can take."""
    validate_lines(lines)
    blocks, current, size = [], [], 0
    seen = set()
    for line in lines:
        speaker = line["speaker"].strip()
        if speaker not in voices:
            raise ValueError(f"Unknown speaker: {speaker}")
        text = line["text"].strip()
        if len(text) + len(ACCENT_CUE) > DIALOGUE_CHARS:
            raise ValueError('Turn exceeds dialogue block limit; edit the script first')
        cue = ACCENT_CUE if speaker not in seen and LANGUAGE == 'ar' else ''
        if current and size + len(text) + len(cue) > DIALOGUE_CHARS:
            blocks.append(current)
            current, size = [], 0
            seen = set()
            cue = ACCENT_CUE if LANGUAGE == 'ar' else ''
        text = cue + text
        current.append({"text": text, "voice_id": voices[speaker]})
        seen.add(speaker)
        size += len(text)
    if current:
        blocks.append(current)
    return blocks


def dialogue_payload(inputs, model):
    if model != 'eleven_v3':
        raise ValueError('Dialogue requires the tested eleven_v3 pipeline; no silent fallback')
    payload = {"inputs": inputs, "model_id": model,
               "settings": {"stability": STABILITY}, "seed": SEED}
    if LANGUAGE:
        payload["language_code"] = LANGUAGE
    return payload


def request_digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()[:24]


def speak_dialogue(inputs, model: str, key: str, dest: Path) -> None:
    """A whole exchange in one pass, so the voices respond to each other."""
    payload = dialogue_payload(inputs, model)
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{API}/text-to-dialogue", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=300) as response:
        dest.write_bytes(response.read())


def audio_seconds(path: Path) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True).stdout)


def dress(body: Path, out: Path) -> None:
    """Top and tail the episode with the theme music.

    The speech is never faded and never delayed into a fade — it begins at
    full volume while the intro's tail is still ringing out underneath it.
    Anything else clips the first words, which is what a crossfade does.
    """
    intro, outro = ASSETS / "intro.mp3", ASSETS / "outro.mp3"
    if not intro.exists() and not outro.exists():
        shutil.copy(body, out)
        print("  no music in assets/ — published without a theme")
        return

    args = ["ffmpeg", "-y", "-loglevel", "error"]
    filters, mixes = [], []
    body_start = 0.0

    if intro.exists():
        intro_len = audio_seconds(intro)
        body_start = max(0.0, intro_len - INTRO_OVERLAP)
        args += ["-i", str(intro)]
        filters.append(
            f"[{len(mixes)}:a]afade=t=out:st={intro_len - INTRO_FADE:.2f}:"
            f"d={INTRO_FADE}[i]")
        mixes.append("[i]")

    args += ["-i", str(body)]
    delay = int(body_start * 1000)
    filters.append(f"[{len(mixes)}:a]adelay={delay}|{delay}[b]")
    mixes.append("[b]")

    if outro.exists():
        outro_at = int((body_start + audio_seconds(body) - OUTRO_OVERLAP) * 1000)
        args += ["-i", str(outro)]
        filters.append(
            f"[{len(mixes)}:a]afade=t=in:st=0:d={OUTRO_FADE_IN},"
            f"adelay={outro_at}|{outro_at}[o]")
        mixes.append("[o]")

    filters.append(f"{''.join(mixes)}amix=inputs={len(mixes)}:"
                   f"duration=longest:dropout_transition=0:normalize=0,"
                   f"alimiter=limit=0.89:level=0:latency=1[a]")
    args += ["-filter_complex", ";".join(filters), "-map", "[a]",
             "-c:a", "libmp3lame", "-b:a", BITRATE, str(out)]
    subprocess.run(args, check=True)
    print(f"  music: intro fades out, speech starts clean at "
          f"{body_start:.1f}s, outro tails in")


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")
    if not EPISODE.exists():
        print("no episode.json — nothing to render")
        return

    episode = json.loads(EPISODE.read_text())
    lines = episode["lines"]
    validate_lines(lines)
    episode['characters'] = sum(len(line['text']) for line in lines)
    print(f"rendering episode {episode['number']:02d}: {len(lines)} lines, "
          f"{episode['characters']:,} characters")

    WORK.mkdir(exist_ok=True)
    # Keep script and request settings alongside reusable blocks. Never erase
    # successful paid generations when a later block or publication fails.
    (WORK / 'script.json').write_text(json.dumps(episode, ensure_ascii=False, indent=2))

    voices = resolve_voices(key)
    model = resolve_model(key)

    blocks = chunk_lines(lines, voices)
    print(f"  {len(blocks)} dialogue block(s)")

    pieces = []
    for index, inputs in enumerate(blocks):
        payload = dialogue_payload(inputs, model)
        part = WORK / f"{request_digest(payload)}.mp3"
        try:
            if part.exists() and audio_seconds(part) > 0:
                print(f"  reusing cached block {index + 1}")
            else:
                speak_dialogue(inputs, model, key, part)
                audio_seconds(part)  # fail before caching an invalid response
            part.with_suffix('.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
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

    from make_intro import ensure_ident
    ensure_ident(key)
    INCOMING.mkdir(parents=True, exist_ok=True)
    preview = os.environ.get('FINTECH_PREVIEW') == '1'
    out = INCOMING / ('quality-preview.mp3' if preview else
                      f"Fintech Pulse Daily Ep. {episode['number']:02d}.mp3")
    candidate = WORK / "finished.mp3"
    dress(body, candidate)

    seconds = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(candidate)],
        check=True, capture_output=True, text=True).stdout)
    if not preview:
        validate_duration(seconds)
    shutil.copyfile(candidate, out)
    print(f"  wrote {out.name} — {int(seconds)//60}:{int(seconds)%60:02d}, "
          f"{out.stat().st_size/1e6:.1f} MB")

    print('  script, request settings and audio blocks retained in .render/')


if __name__ == "__main__":
    main()
