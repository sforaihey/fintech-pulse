"""Research today's fintech news and write the two-host script.

Runs in CI. Uses Claude with the server-side web search tool, so there is no
scraping to maintain -- the model does the searching and we get back a script
already inside the character budget.

Output: episode.json  {"number", "date", "product", "stories", "notes",
                       "lines": [{"speaker": "DANA"|"ADAM", "text": ...}]}
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "episode.json"
RAW = "https://raw.githubusercontent.com/sforaihey/fintech-pulse/main"

RIYADH = timezone(timedelta(hours=3))
MODEL = "claude-opus-5"
CHAR_BUDGET = int(os.environ.get("FINTECH_CHAR_BUDGET", "7500"))

SYSTEM = """You write "Fintech Pulse Daily", a two-host audio briefing for one \
listener: a Saudi banking product manager who works in merchant acquiring and \
corporate onboarding. She knows banking well — never explain what a POS \
terminal or an IBAN is. She does not know the whole product landscape, which \
is why every episode teaches her one product properly.

THE HOSTS
  DANA — anchors the episode. Warm, quick, a little sceptical. She asks the
  question the listener is actually thinking, and she pushes back when Adam
  glosses over something.
  ADAM — the analyst. Dry, precise, occasionally opinionated. He has numbers
  and he has views, and he is not always right.

THIS IS A CONVERSATION, NOT A BULLETIN. That distinction is the whole point of
the show, so write it the way two colleagues actually talk:

  - They interrupt each other. They finish each other's thoughts. They react
    before they respond — "Wait." / "Hold on." / "Hmm." / "Oh, that's clever."
  - They disagree, genuinely, and neither always wins. Adam takes a position;
    Dana tests it. Sometimes she changes his mind.
  - They think out loud. Half-formed thoughts, a correction mid-sentence, a
    "let me put it another way" — this is what makes speech sound human.
  - They are funny occasionally, dry rather than jokey.
  - Short lines matter. A three-word reaction between two longer turns is what
    gives a conversation its rhythm. A script where every line is three
    sentences long sounds like two press releases being read aloud.

DELIVERY MARKUP — the voice model performs these, so use them:
  - Audio tags in square brackets for genuine reactions: [laughs], [sighs],
    [thoughtful], [skeptical], [surprised], [dry], [amused]. Use them where a
    person would really do that — a handful per episode, not every line.
  - Ellipses (...) create a real pause and hesitation.
  - CAPITALS on a word for emphasis.
  - Dashes for a cut-off — where one host talks over the other.

Sourcing: prefer regulator announcements, company statements and reputable \
financial press. Use concrete figures and name organisations. If a claim \
cannot be sourced, leave it out rather than softening it. But deliver the \
figures conversationally — "call it three and a quarter trillion riyals" not \
"SAR 3.25 trillion"."""


def fetch(path: str) -> str:
    try:
        with urllib.request.urlopen(f"{RAW}/{path}", timeout=30) as response:
            return response.read().decode()
    except Exception as exc:                     # noqa: BLE001 - report and go on
        print(f"  warning: could not read {path}: {exc}")
        return ""


def next_episode_number() -> int:
    try:
        return max(int(k) for k in json.loads(fetch("episodes.json"))) + 1
    except Exception:                            # noqa: BLE001
        sys.exit("could not determine the next episode number from episodes.json")


def script_chars(lines) -> int:
    return sum(len(line["text"]) for line in lines)


def build_prompt(number: int, today, covered: str) -> str:
    return f"""Write episode {number:02d} of Fintech Pulse Daily for \
{today:%A %-d %B %Y} (Riyadh).

Search the web for what actually happened in the last 24 hours, in two areas:
  (a) SAUDI ARABIA — SAMA regulation and licensing, local banks, payments,
      Saudi fintech funding, Vision 2030 financial-sector moves.
  (b) GLOBAL — anything materially important in payments, banking, crypto and
      tokenisation, embedded finance, or AI in financial services.

Then pick ONE fintech product or product category to explain properly. It must
not be one of these, which previous episodes already covered:

{covered or "(nothing covered yet)"}

Explain what it does, the problem it solves, the notable providers globally and
in Saudi/GCC, how the money flows, and what a bank or PSP must do to offer it.
Give this segment about 40 percent of the script — it is the part she values
most. Teach it through the conversation: Dana asking the naive question, Adam
answering, Dana finding the edge case. Not a lecture from Adam.

LENGTH: aim for roughly {CHAR_BUDGET:,} characters of spoken text across all
lines — that is about {CHAR_BUDGET // 900} minutes. Do not pad to reach it and do not
race to stay under it; write the conversation the story deserves and let it
land near that mark. Aim for 70 to 100 lines, deliberately uneven in length.

Running order: short cold open on the biggest story, Saudi news, global news,
the product segment, then a brief close on what to watch tomorrow.

Reply with ONLY a JSON object in a ```json fence:
{{
  "product": "name of the product explained",
  "product_note": "one line for the covered-products log",
  "stories": ["story one", "story two", "story three"],
  "notes": "show notes in markdown, including a Sources list with links",
  "lines": [{{"speaker": "DANA", "text": "..."}}, ...]
}}"""


def call_claude(client, prompt: str):
    """One turn, resuming across pause_turn, with the fallback beta if allowed."""
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12}]
    kwargs = dict(model=MODEL, max_tokens=32000, system=SYSTEM,
                  thinking={"type": "adaptive"}, tools=tools)
    use_fallback = True

    for attempt in range(6):
        try:
            if use_fallback:
                stream = client.beta.messages.stream(
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default", messages=messages, **kwargs)
            else:
                stream = client.messages.stream(messages=messages, **kwargs)
            with stream as active:
                message = active.get_final_message()
        except anthropic.BadRequestError as exc:
            if use_fallback:
                print(f"  fallback params rejected ({exc}); retrying without")
                use_fallback = False
                continue
            raise

        if message.stop_reason == "refusal":
            sys.exit(f"request refused: {message.stop_details}")
        if message.stop_reason == "pause_turn":
            print("  pause_turn — resuming")
            messages += [{"role": "assistant", "content": message.content}]
            continue
        return message

    sys.exit("gave up after repeated pause_turn resumptions")


def extract_json(message) -> dict:
    text = "".join(b.text for b in message.content if b.type == "text")
    fenced = re.search(r"```json\s*(.+?)```", text, re.S)
    raw = fenced.group(1) if fenced else text[text.find("{"):text.rfind("}") + 1]
    return json.loads(raw)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")

    today = datetime.now(RIYADH).date()
    if today.weekday() in (4, 5):
        print(f"{today:%A} — the show runs Sunday to Thursday. Nothing to do.")
        return

    number = next_episode_number()
    covered = fetch("docs/products-covered.md")
    print(f"writing episode {number:02d} for {today}")

    client = anthropic.Anthropic(timeout=900.0)
    message = call_claude(client, build_prompt(number, today, covered))
    episode = extract_json(message)

    used = script_chars(episode["lines"])
    print(f"  {len(episode['lines'])} lines, {used:,} characters "
          f"(budget {CHAR_BUDGET:,})")

    # Only a runaway gets cut: trimming the tail costs the episode its ending,
    # so tolerate overshoot and intervene only when the spend is unreasonable.
    ceiling = int(CHAR_BUDGET * 1.3)
    if used > ceiling:
        while episode["lines"] and script_chars(episode["lines"]) > ceiling:
            episode["lines"].pop()
        print(f"  over {ceiling:,} — trimmed to "
              f"{script_chars(episode['lines']):,} characters")

    episode.update(number=number, date=today.isoformat(),
                   characters=script_chars(episode["lines"]))
    OUT.write_text(json.dumps(episode, indent=2, ensure_ascii=False))
    print(f"  wrote {OUT.name}")


if __name__ == "__main__":
    main()
