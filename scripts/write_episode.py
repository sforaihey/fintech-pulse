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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "episode.json"
RAW = "https://raw.githubusercontent.com/sforaihey/fintech-pulse/main"

RIYADH = timezone(timedelta(hours=3))
MODEL = "claude-opus-5"
CHAR_BUDGET = int(os.environ.get("FINTECH_CHAR_BUDGET", "11000"))
# Backfill support: write an episode for a past date instead of today.
EPISODE_DATE = os.environ.get("FINTECH_DATE", "")
EPISODE_NUMBER = os.environ.get("FINTECH_EPISODE", "")

SYSTEM = """You write "Fintech Pulse Daily", a two-host audio briefing for one \
listener: a Saudi banking product manager who works in merchant acquiring and \
corporate onboarding. She knows banking well — never explain what a POS \
terminal or an IBAN is. She does not know the whole product landscape, which \
is why every episode teaches her one product properly.

WHAT YOU ARE WRITING
Two knowledgeable fintech people having a spontaneous conversation — not two
presenters reading a script. They discuss the news, react to it, challenge each
other respectfully, and explain why it matters.

THE HOSTS, WHO MUST SOUND DIFFERENT FROM EACH OTHER
  DANA — curious and quick. She comes at things from the customer and the
  operator: who actually has to build this, who pays for it, what breaks. She
  asks the genuine follow-up, and she says when something does not add up.
  ADAM — analytical and dry. He reaches for the number, the precedent, the
  structural reason. He takes positions and defends them, and he is sometimes
  wrong, and when Dana catches him he concedes.

HOW REAL CONVERSATION WORKS — this is the whole craft of the show
  - Genuine follow-up questions. Not "tell me more", but the specific question
    that follows from what was just said.
  - Reactions before responses. "Hm." / "Wait, really?" / "Okay, that I did
    not expect."
  - Respectful disagreement that goes somewhere. One of them changes position
    at least once an episode.
  - Varied sentence length. Some lines are one word. Some run long because the
    speaker is thinking as they talk.
  - Light humour, dry, arising from the material. Never a set-up joke.
  - Brief pauses where a person would actually pause.

WHAT KILLS IT — avoid all of these
  - Long monologues. If a turn runs past four sentences, break it and let the
    other host interject.
  - Forced jokes, and any joke that is not about what they are discussing.
  - Repetitive summaries — do not restate what was just said in other words.
  - Robotic transitions. Never "moving on to our next story" or "so to recap".
    Real conversations change subject because something reminds someone of
    something.

DELIVERY MARKUP — the voice model performs these
  - Audio tags for real reactions: [laughs], [sighs], [thoughtful],
    [skeptical], [surprised], [dry], [amused]. A handful per episode, only
    where a person would genuinely do that.
  - Ellipses (...) for a real pause or hesitation.
  - CAPITALS on one word for emphasis.
  - A dash at the end of a line — where the other host cuts in.

ACCURACY IS NOT NEGOTIABLE
Never invent a fact, a figure, a quote, or an opinion attributed to a real
person or company. Every number and claim must come from something you found.
If you cannot source it, leave it out — the show is worthless to her if she
repeats something at work that turns out to be made up.

FIGURES ARE FOR A RIYADH LISTENER
Deliver them conversationally: "call it three and a quarter trillion riyals",
not "SAR 3.25 trillion". Any figure quoted in a foreign currency gets its
riyal equivalent spoken alongside it, the way a colleague would — "eighty
million dollars, so about three hundred million riyals". The riyal is pegged
at 3.75 to the dollar, so dollar conversions are exact; for other currencies
use the rate you find and round sensibly rather than implying precision you do
not have. Do not convert a figure twice in the same breath, and skip the
conversion where it adds nothing — a share price or a percentage does not need
one."""


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


def previous_publishing_day(day):
    """The last Sunday-to-Thursday day before `day`."""
    earlier = day - timedelta(days=1)
    while earlier.weekday() in (4, 5):
        earlier -= timedelta(days=1)
    return earlier


def build_prompt(number: int, today, covered: str, recent: str = "") -> str:
    covered_block = covered or "(nothing covered yet — pick any product)"
    since = previous_publishing_day(today)
    span = (today - since).days
    window = (f"since the previous episode went out on {since:%A %-d %B} — that "
              f"is {span} day{'s' if span > 1 else ''} of news, including the "
              f"weekend" if span > 1 else
              f"since the previous episode went out on {since:%A %-d %B}")
    recent_block = recent or "(no earlier episodes)"
    return f"""Write episode {number:02d} of Fintech Pulse Daily for \
{today:%A %-d %B %Y} (Riyadh).

Search the web for what happened {window}, up to the morning of
{today:%-d %B %Y}. Report the news as it stood then, not as it stands now.
Nothing that happened over a Friday or Saturday should be lost — if this
episode follows a weekend, those two days are part of your window. Two areas:
  (a) SAUDI ARABIA — SAMA regulation and licensing, local banks, payments,
      Saudi fintech funding, Vision 2030 financial-sector moves.
  (b) GLOBAL — anything materially important in payments, banking, crypto and
      tokenisation, embedded finance, or AI in financial services.

FINTECH PRODUCT SPOTLIGHT — every episode has one, and it is the segment she
values most. Pick ONE real, named product that is not already covered:

{covered_block}

Teach it as a lively discussion — Adam explaining, Dana asking the practical
questions and offering a different angle. Educational and balanced, never
promotional. Cover all of these, in whatever order the conversation reaches
them:
  - what the product does, and who it serves
  - what problem it solves
  - how the customer experience actually works, step by step
  - how the company makes money from it
  - its strengths, its limitations, and who it competes with
  - one useful lesson a fintech professional can take from it

Give the spotlight about 40 percent of the script.

LENGTH: aim for roughly {CHAR_BUDGET:,} characters of spoken text across all
lines — that is about {CHAR_BUDGET // 900} minutes. Do not pad to reach it and do not
race to stay under it; write the conversation the story deserves and let it
land near that mark. Aim for 70 to 100 lines, deliberately uneven in length.

Running order: short cold open on the biggest story, Saudi news, global news,
the product segment, then a brief close on what to watch tomorrow.

ALREADY REPORTED in recent episodes — do not re-report these as if they were
new. You may return to one only if there is genuinely new information today,
and if you do, lead with what changed rather than restating the story:

{recent_block}

Reply with ONLY a JSON object in a ```json fence:
{{
  "title": "a real episode title — what today is about, not a date. Six to
            nine words, no 'Ep. NN' prefix, no colon-subtitle padding",
  "summary": "two or three sentences someone browsing a podcast app would read
              to decide whether to listen. Name the actual stories.",
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
        except anthropic.APIStatusError as exc:
            # Billing problems are the common one and deserve a plain sentence
            # rather than a traceback in a CI log nobody wants to read.
            if "credit balance" in str(exc) or "billing" in str(exc).lower():
                sys.exit("The Anthropic API account is out of credit. Top it up "
                         "at console.anthropic.com -> Plans & Billing. This is "
                         "separate from the Claude subscription and from "
                         "ElevenLabs.")
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

    if EPISODE_DATE:
        today = date.fromisoformat(EPISODE_DATE)
        print(f"backfilling for {today:%A %-d %B %Y}")
    else:
        today = datetime.now(RIYADH).date()
        if today.weekday() in (4, 5):
            print(f"{today:%A} — the show runs Sunday to Thursday. Nothing to do.")
            return

    number = int(EPISODE_NUMBER) if EPISODE_NUMBER else next_episode_number()
    covered = fetch("docs/products-covered.md")
    recent = fetch("docs/recent-stories.md")
    print(f"writing episode {number:02d} for {today}")

    client = anthropic.Anthropic(timeout=900.0)
    message = call_claude(client, build_prompt(number, today, covered, recent))
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
