"""Render a fixed Najdi script with two Arabic voices, to judge the idea.

Deliberately not written by the model: the script is the one already reviewed,
so what is being judged here is pronunciation and delivery, nothing else.
Three renders isolate whether telling ElevenLabs the language helps, and
whether the dialogue endpoint or line-by-line sounds better in Arabic.

Needs ELEVENLABS_API_KEY. Costs roughly three times the script length.
"""

import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_episode as R                                    # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "sample-ar"
WORK = REPO / ".sample-ar"

VOICES = {
    "سلطان": "rUaPbzcZIu8df8iNL9WZ",   # anchor
    "فيصل": "wyC6KvCMTAXGbiCKlfSx",    # analyst
}

# The reviewed script, with the hosts renamed for two male voices. English
# technical terms are left in English, which is how the conversation would
# actually happen in Riyadh -- and is the hardest thing for Arabic TTS.
SCRIPT = [
    ("سلطان", "طيب، ساما فتحت الترخيص للـ open banking رسمياً. طلعوا من الـ sandbox."),
    ("فيصل", "[thoughtful] ايه... وهذي مو خطوة صغيرة ترى."),
    ("سلطان", "وش يعني عملياً للبنك؟"),
    ("فيصل", "يعني الحين أي شركة fintech تبي توصل لبيانات العميل لازم يكون عندها ترخيص كامل. مو تجربة."),
    ("سلطان", "[skeptical] طيب بس... البنوك وش يستفيدون؟ هم اللي يفتحون بياناتهم."),
    ("فيصل", "[dry] هذا السؤال الصح. نظرياً سرعة في الـ onboarding. عملياً ضغط تنافسي."),
    ("سلطان", "كذا أنا أشوفها. تفتح الـ API وتصير أنت الـ infrastructure، وغيرك ياخذ العميل."),
    ("فيصل", "...صح. هذي نقطة."),
    ("سلطان", "وتدري وش اللي يخوف أكثر؟ الـ consent management. لو العميل ما فهم وش وافق عليه، المشكلة ترجع للبنك مو للـ fintech."),
    ("فيصل", "[dry] والمنظم بيسأل البنك أول."),
    ("سلطان", "[amused] بالضبط."),
    ("فيصل", "تمارا مثلاً — إيراد الربع الثاني سبعمية وسبعة مليون ريال، زيادة مية واثنين وخمسين بالمية."),
    ("سلطان", "[surprised] كم؟"),
    ("فيصل", "بس صافي الربح نزل. أربعة وثمانين مليون، نازل اثنين وثلاثين بالمية."),
]

VARIANTS = [
    ("sultan-faisal", "Sultan and Faisal — dialogue, Arabic", "dialogue", "ar"),
]


def speak_dialogue(inputs, model, key, dest, language):
    payload = {"inputs": inputs, "model_id": model,
               "settings": {"stability": 0.35}}
    if language:
        payload["language_code"] = language
    request = urllib.request.Request(
        f"{R.API}/text-to-dialogue", data=json.dumps(payload).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=300) as response:
        dest.write_bytes(response.read())


def speak_line(text, voice_id, model, key, dest, language):
    payload = {"text": text, "model_id": model,
               "voice_settings": {"stability": 0.35, "similarity_boost": 0.8}}
    if language:
        payload["language_code"] = language
    request = urllib.request.Request(
        f"{R.API}/text-to-speech/{voice_id}", data=json.dumps(payload).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    with urllib.request.urlopen(request, timeout=180) as response:
        dest.write_bytes(response.read())


def render(name, mode, language, key, model):
    WORK.mkdir(exist_ok=True)
    for stale in WORK.iterdir():
        stale.unlink()

    pieces = []
    if mode == "dialogue":
        inputs = [{"text": t, "voice_id": VOICES[s]} for s, t in SCRIPT]
        block, size, blocks = [], 0, []
        for item in inputs:
            if block and size + len(item["text"]) > R.DIALOGUE_CHARS:
                blocks.append(block); block, size = [], 0
            block.append(item); size += len(item["text"])
        if block:
            blocks.append(block)
        for index, chunk in enumerate(blocks):
            part = WORK / f"{index:03d}.mp3"
            speak_dialogue(chunk, model, key, part, language)
            pieces.append(part)
    else:
        for index, (speaker, text) in enumerate(SCRIPT):
            part = WORK / f"{index:03d}.mp3"
            speak_line(text, VOICES[speaker], model, key, part, language)
            pieces.append(part)

    listing = WORK / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in pieces))
    dest = OUT / f"{name}.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c:a", "libmp3lame", "-b:a", R.BITRATE,
         str(dest.resolve())], check=True, cwd=WORK)
    print(f"  {name}: {dest.stat().st_size / 1e6:.1f} MB")
    return dest.name


def page(rendered):
    rows = "\n".join(
        f'      <p><b>{html.escape(s)}</b> {html.escape(t)}</p>'
        for s, t in SCRIPT)
    clips = "\n".join(
        f'''      <div class="clip"><div class="label">{html.escape(label)}</div>
        <audio controls preload="none" src="{html.escape(f)}"></audio></div>'''
        for label, f in rendered)
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fintech Pulse — Arabic test</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b1325; color:#e8edf7; padding:2.5rem 1.15rem 5rem;
         font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  main {{ max-width:36rem; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .4rem; }}
  .lede {{ color:#93a1ba; margin:0 0 2rem; }}
  h2 {{ font-size:1rem; margin:2.2rem 0 .8rem; }}
  .clip {{ background:#141e36; border:1px solid #26334f; border-radius:12px;
           padding:.9rem 1rem; margin-bottom:.8rem; }}
  .label {{ font-size:.88rem; color:#93a1ba; margin-bottom:.55rem; }}
  audio {{ width:100%; }}
  .script {{ direction:rtl; text-align:right; }}
  .script p {{ margin:0 0 .75rem; font-size:1.02rem; }}
  .script b {{ color:#2ec9a5; margin-left:.4rem; }}
  .listen {{ border-left:2px solid #E0A34A; padding-left:.85rem;
             color:#93a1ba; font-size:.92rem; margin:0 0 2rem; }}
</style>
<main>
  <h1>Arabic test — Sultan and Faisal</h1>
  <p class="lede">The same Najdi script, one straight render with expressions.</p>
  <p class="listen">Listen for the accent, the spoken numbers, whether the
     English terms survive, and whether the two voices are distinct.</p>
{clips}
  <h2>النص</h2>
  <div class="script">
{rows}
  </div>
</main>
"""


def main():
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")

    chars = sum(len(t) for _, t in SCRIPT)
    print(f"{len(SCRIPT)} lines, {chars:,} characters")
    OUT.mkdir(exist_ok=True)
    model = R.resolve_model(key)

    rendered = []
    for name, label, mode, language in VARIANTS:
        try:
            rendered.append((label, render(name, mode, language, key, model)))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:250]
            print(f"  ! {name}: HTTP {exc.code} — {detail}")

    (OUT / "index.html").write_text(page(rendered))
    for leftover in WORK.iterdir():
        leftover.unlink()
    WORK.rmdir()
    print(f"\nwrote sample-ar/index.html — about {chars * len(rendered):,} credits")


if __name__ == "__main__":
    main()
