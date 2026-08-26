"""Produce a short two-host clip so voices and script style can be judged cheaply.

Writes about a minute of conversation and renders it three ways, because the
web app's preview and the API can sound different and it is worth knowing
which knob is responsible:

  A  dialogue endpoint, expressive stability   (what the show uses now)
  B  dialogue endpoint, natural stability
  C  line-by-line text-to-speech, natural      (closest to the web preview)

Publishes sample/index.html. Costs roughly three times the clip length in
credits — a fraction of an episode.
"""

import html
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_episode as R                                    # noqa: E402
from write_episode import SYSTEM, call_claude, extract_json    # noqa: E402

import anthropic                                              # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "sample"
WORK = REPO / ".sample"
CLIP_CHARS = int(os.environ.get("FINTECH_SAMPLE_CHARS", "950"))

VARIANTS = [
    ("a-dialogue-expressive", "Dialogue endpoint, expressive (0.35)", "dialogue", 0.35),
    ("b-dialogue-natural", "Dialogue endpoint, natural (0.5)", "dialogue", 0.50),
    ("c-lines-natural", "Line by line, natural (0.5)", "lines", 0.50),
]

PROMPT = f"""Write a SHORT sample of Fintech Pulse Daily — about {CLIP_CHARS}
characters of spoken text, roughly 12 to 16 lines. This is a test clip used to
judge how the hosts sound, so it must show the show at its most characteristic.

Do not research anything. Use this as the material, which is real:

  Visa is looking for a new stablecoin settlement partner, and the mandate asks
  for licensing across the US, Canada and Europe.

In these few lines the clip must contain, naturally:
  - a genuine reaction before a response
  - a real follow-up question from Dana
  - Adam taking a position, and Dana pushing back on it
  - one dry, quiet piece of humour arising from the material
  - at least one very short line and one longer thinking-aloud line

Do not summarise, do not introduce the show, do not sign off. Drop the listener
straight into the middle of the conversation.

Reply with ONLY a JSON object in a ```json fence:
{{"lines": [{{"speaker": "DANA", "text": "..."}}, ...]}}"""


def render(name: str, lines, mode: str, stability: float, key: str, model: str):
    R.STABILITY = stability
    dest = OUT / f"{name}.mp3"
    WORK.mkdir(exist_ok=True)
    for stale in WORK.iterdir():
        stale.unlink()

    if mode == "dialogue":
        blocks = R.chunk_lines(lines, R.VOICES)
        pieces = []
        for index, inputs in enumerate(blocks):
            part = WORK / f"{index:03d}.mp3"
            R.speak_dialogue(inputs, model, key, part)
            pieces.append(part)
    else:
        pieces = []
        for index, line in enumerate(lines):
            voice = R.VOICES.get(line["speaker"].upper())
            if not voice:
                continue
            part = WORK / f"{index:03d}.mp3"
            R.speak(line["text"], voice, model, key, part)
            pieces.append(part)

    listing = WORK / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in pieces))
    import subprocess
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listing.name, "-c:a", "libmp3lame", "-b:a", R.BITRATE,
         str(dest.resolve())], check=True, cwd=WORK)
    print(f"  {name}: {dest.stat().st_size / 1e6:.1f} MB")
    return dest.name


def page(script, rendered) -> str:
    transcript = "\n".join(
        f'      <p><b>{html.escape(l["speaker"].title())}</b> '
        f'{html.escape(l["text"])}</p>' for l in script)
    clips = "\n".join(
        f'''      <div class="clip">
        <div class="label">{html.escape(label)}</div>
        <audio controls preload="none" src="{html.escape(file)}"></audio>
      </div>''' for label, file in rendered)
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fintech Pulse — sample</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b1325; color:#e8edf7; padding:2.5rem 1.15rem 5rem;
         font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  main {{ max-width:36rem; margin:0 auto; }}
  h1 {{ font-size:1.6rem; margin:0 0 .4rem; letter-spacing:-.02em; }}
  .lede {{ color:#93a1ba; margin:0 0 2.2rem; }}
  h2 {{ font-size:1rem; margin:2.2rem 0 .8rem; }}
  .clip {{ background:#141e36; border:1px solid #26334f; border-radius:12px;
           padding:.9rem 1rem; margin-bottom:.8rem; }}
  .label {{ font-size:.88rem; color:#93a1ba; margin-bottom:.55rem; }}
  audio {{ width:100%; }}
  .script p {{ margin:0 0 .7rem; font-size:.94rem; }}
  .script b {{ color:#2ec9a5; margin-right:.35rem; }}
</style>
<main>
  <h1>Sample clip</h1>
  <p class="lede">The same short conversation, rendered three ways. Tell me
     which sounds right — and whether the writing itself works.</p>
{clips}
  <h2>What they are saying</h2>
  <div class="script">
{transcript}
  </div>
</main>
"""


def main() -> None:
    el_key = os.environ.get("ELEVENLABS_API_KEY")
    if not el_key or not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("both ELEVENLABS_API_KEY and ANTHROPIC_API_KEY are needed")

    print("writing the clip")
    message = call_claude(anthropic.Anthropic(timeout=600.0), PROMPT)
    lines = extract_json(message)["lines"]
    total = sum(len(l["text"]) for l in lines)
    print(f"  {len(lines)} lines, {total:,} characters")

    OUT.mkdir(exist_ok=True)
    model = R.resolve_model(el_key)
    R.resolve_voices(el_key)

    rendered = []
    for name, label, mode, stability in VARIANTS:
        try:
            rendered.append((label, render(name, lines, mode, stability,
                                           el_key, model)))
        except urllib.error.HTTPError as exc:
            print(f"  ! {name}: HTTP {exc.code} "
                  f"{exc.read().decode('utf-8', 'replace')[:200]}")

    (OUT / "index.html").write_text(page(lines, rendered))
    for leftover in WORK.iterdir():
        leftover.unlink()
    WORK.rmdir()
    print(f"\nwrote sample/index.html — about {total * len(rendered):,} credits")


if __name__ == "__main__":
    main()
