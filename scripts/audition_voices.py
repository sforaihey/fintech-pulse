"""Render the same two lines in several voices so they can be compared.

Publishes auditions/index.html on GitHub Pages: open it on a phone, listen,
pick one voice for each host. Cheap -- about 230 characters per voice.
"""

import html
import json
import os
import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_episode import api_get, match_voice, resolve_model, speak  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "auditions"

# Lines from the show itself, so each voice is heard doing the real job.
LINES = {
    "anchor": (
        "Good morning. SAMA has published its updated payment services rules, "
        "and buried in the annex is a change that touches every acquirer in "
        "the Kingdom. Sami — is this as big as it looks?"),
    "analyst": (
        "Bigger, honestly. The headline is settlement timing, but the real "
        "story is paragraph four: they have redefined who holds the funds in "
        "transit. If you run a partner switch, that changes your capital "
        "treatment overnight."),
}

CANDIDATES = {
    "anchor": ["Sarah", "Matilda", "Alice", "River", "Lauren"],
    "analyst": ["Daniel", "Eric", "Bill", "Brian", "Nate"],
}

ROLE_TITLE = {
    "anchor": ("LAYLA — the anchor",
               "Opens the episode, sets the running order, asks the questions."),
    "analyst": ("SAMI — the analyst",
                "Explains the mechanics, gives the numbers, takes positions."),
}

CURRENT = {"anchor": "Lauren", "analyst": "Nate"}


def page(rendered: dict) -> str:
    sections = []
    for role, voices in rendered.items():
        title, blurb = ROLE_TITLE[role]
        cards = "\n".join(
            f"""      <div class="voice">
        <div class="meta">
          <span class="name">{html.escape(name)}</span>
          <span class="desc">{html.escape(desc)}</span>
          {'<span class="tag">currently used</span>' if name == CURRENT[role] else ''}
        </div>
        <audio controls preload="none" src="{html.escape(file)}"></audio>
      </div>"""
            for name, desc, file in voices)
        sections.append(f"""    <section>
      <h2>{html.escape(title)}</h2>
      <p class="blurb">{html.escape(blurb)}</p>
      <p class="script">"{html.escape(LINES[role])}"</p>
{cards}
    </section>""")

    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fintech Pulse — voice auditions</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; background:#0b1325; color:#e8edf7; padding:2.5rem 1.15rem 5rem;
         font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
  main {{ max-width:36rem; margin:0 auto; }}
  h1 {{ font-size:1.7rem; margin:0 0 .4rem; letter-spacing:-.02em; }}
  .lede {{ color:#93a1ba; margin:0 0 2.5rem; }}
  section {{ margin-bottom:3rem; }}
  h2 {{ font-size:1.05rem; margin:0 0 .2rem; }}
  .blurb {{ color:#93a1ba; margin:0 0 .9rem; font-size:.93rem; }}
  .script {{ color:#7d8aa3; font-size:.85rem; font-style:italic;
             border-left:2px solid #26334f; padding-left:.8rem; margin:0 0 1.5rem; }}
  .voice {{ background:#141e36; border:1px solid #26334f; border-radius:12px;
            padding:.9rem 1rem; margin-bottom:.8rem; }}
  .meta {{ display:flex; align-items:baseline; gap:.5rem; flex-wrap:wrap;
           margin-bottom:.6rem; }}
  .name {{ font-weight:600; }}
  .desc {{ color:#93a1ba; font-size:.85rem; }}
  .tag {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.08em;
          color:#04261d; background:#2ec9a5; border-radius:99px; padding:.1rem .5rem; }}
  audio {{ width:100%; }}
</style>
<main>
  <h1>Which voices?</h1>
  <p class="lede">Same lines, different voices. Listen to each and tell me one
     for the anchor and one for the analyst — then I'll set them and the show
     uses them from the next episode.</p>
{chr(10).join(sections)}
</main>
"""


def main() -> None:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set")

    catalogue = {v["name"].strip().lower(): v["voice_id"]
                 for v in api_get("voices", key).get("voices", [])}
    descriptions = {v["name"].strip().lower(): v["name"]
                    for v in api_get("voices", key).get("voices", [])}
    model = resolve_model(key)

    OUT.mkdir(exist_ok=True)
    rendered, spent = {}, 0

    for role, names in CANDIDATES.items():
        rendered[role] = []
        for name in names:
            voice_id = match_voice(name, catalogue)
            if not voice_id:
                print(f"  ! {name} not in the library, skipping")
                continue
            dest = OUT / f"{role}-{name.lower()}.mp3"
            try:
                speak(LINES[role], voice_id, model, key, dest)
            except urllib.error.HTTPError as exc:
                print(f"  ! {name}: HTTP {exc.code}")
                continue
            spent += len(LINES[role])
            full = next((descriptions[k] for k in descriptions
                         if match_voice(name, {k: 1})), name)
            desc = full.split(" - ", 1)[1] if " - " in full else ""
            rendered[role].append((name, desc, dest.name))
            print(f"  {role}: {name} -> {dest.name}")

    (OUT / "index.html").write_text(page(rendered))
    print(f"\nwrote auditions/index.html — {spent:,} characters spent")


if __name__ == "__main__":
    main()
