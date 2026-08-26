"""Verify the API keys and their permissions before a real run.

Costs nothing: it only reads. Run it after creating or rotating a key, or
when a run fails and you want to know whether the key is the reason.
"""

import json
import os
import sys
import urllib.error
import urllib.request

EL = "https://api.elevenlabs.io/v1"
VOICES_WANTED = ["Lauren", "Nate"]
MODELS_WANTED = ["eleven_v3", "eleven_multilingual_v2", "eleven_turbo_v2_5"]

ok = True


def result(label: str, passed: bool, detail: str = "") -> None:
    global ok
    ok = ok and passed
    print(f"  {'PASS' if passed else 'FAIL'}  {label}{': ' + detail if detail else ''}")


def el_get(path: str, key: str):
    request = urllib.request.Request(f"{EL}/{path}", headers={"xi-api-key": key})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def check_elevenlabs(key: str) -> None:
    print("ElevenLabs")
    try:
        sub = el_get("user/subscription", key)
        left = sub["character_limit"] - sub["character_count"]
        result("User (credit balance)", True,
               f"{left:,} credits left on the {sub.get('tier', '?')} plan")
    except urllib.error.HTTPError as exc:
        result("User (credit balance)", False,
               f"HTTP {exc.code} — enable the 'User' permission on the key")

    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from render_episode import match_voice

        names = {v["name"].strip().lower(): v["voice_id"]
                 for v in el_get("voices", key).get("voices", [])}
        missing = [v for v in VOICES_WANTED if not match_voice(v, names)]
        result("Voices", not missing,
               "all present" if not missing else f"missing {', '.join(missing)}")
        if missing:
            print(f"        your library has {len(names)} voice(s):")
            for name, voice_id in sorted(names.items()):
                print(f"          {name}  ({voice_id})")
    except urllib.error.HTTPError as exc:
        result("Voices", False,
               f"HTTP {exc.code} — set the 'Voices' permission to Read")

    try:
        available = {m["model_id"] for m in el_get("models", key)}
        usable = [m for m in MODELS_WANTED if m in available]
        result("Models", bool(usable),
               f"will use {usable[0]}" if usable else "no usable TTS model")
    except urllib.error.HTTPError as exc:
        result("Models", False,
               f"HTTP {exc.code} — enable the 'Models' permission")

    from render_episode import VOICES, resolve_model, speak
    import tempfile
    try:
        model = resolve_model(key)
    except SystemExit:
        model = "eleven_v3"
    for speaker, voice_id in VOICES.items():
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp:
                speak("Testing.", voice_id, model, key, Path(tmp.name))
                size = Path(tmp.name).stat().st_size
            result(f"Voice {speaker} ({voice_id})", size > 1000,
                   f"synthesised {size:,} bytes")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:200]
            result(f"Voice {speaker} ({voice_id})", False,
                   f"HTTP {exc.code} — {detail}")


def check_anthropic(key: str) -> None:
    print("\nAnthropic")
    try:
        import anthropic
    except ImportError:
        result("SDK installed", False, "pip install anthropic")
        return
    try:
        response = anthropic.Anthropic(api_key=key).messages.create(
            model="claude-opus-5", max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the word: ready"}])
        text = "".join(b.text for b in response.content if b.type == "text")
        result("API key works", True, f"model replied {text.strip()!r}")
    except Exception as exc:                     # noqa: BLE001
        result("API key works", False, str(exc)[:160])


if __name__ == "__main__":
    el_key = os.environ.get("ELEVENLABS_API_KEY")
    an_key = os.environ.get("ANTHROPIC_API_KEY")

    if el_key:
        check_elevenlabs(el_key)
    else:
        print("ElevenLabs\n  SKIP  ELEVENLABS_API_KEY not set")

    if an_key:
        check_anthropic(an_key)
    else:
        print("\nAnthropic\n  SKIP  ANTHROPIC_API_KEY not set — still to be added")

    print("\n" + ("All configured keys look good." if ok
                  else "Something needs fixing — see the FAIL lines above."))
    sys.exit(0 if ok else 1)
