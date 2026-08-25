# Fintech Pulse — episode task

Paste the block below into the claude.ai scheduled task **Fintech Pulse —
daily episode** (leave the dashboard task alone).

- **Frequency:** Daily · 07:15 AM — *not* "Weekdays", which means Mon–Fri.
  The Sunday–Thursday rule is enforced inside the instructions instead.
- **Permissions:** Automatically approve.
- **Connectors:** **GitHub** must be switched on *for this task*. Connectors
  are enabled per conversation on claude.ai, so an account-level connection is
  not enough — open the task and enable GitHub on it.

Reads use the repo's public raw URLs (no permissions needed); only the final
commit uses the connector. If GitHub cannot be enabled on the task, see
`docs/delivery.md` for the Notion fallback.

---

```
Produce today's episode of "Fintech Pulse Daily", a two-host audio briefing,
and deliver it for publishing.

STEP 0 — DAY CHECK. Work out today's day of the week in Riyadh (UTC+3). If it
is Friday or Saturday, STOP NOW and produce nothing at all: this show runs
Sunday to Thursday only. Do not generate audio, do not upload anything.

STEP 1 — EPISODE NUMBER. Fetch this URL:
    https://raw.githubusercontent.com/sforaihey/fintech-pulse/main/episodes.json
Take the highest episode number in it and add 1. That is today's episode
number, written with two digits (e.g. 03). If the file cannot be read, STOP
and report the failure rather than guessing — a duplicate number overwrites an
existing episode.

STEP 2 — WHAT ALREADY GOT COVERED. Fetch this URL:
    https://raw.githubusercontent.com/sforaihey/fintech-pulse/main/docs/products-covered.md
It lists the fintech products explained in previous episodes. You must not
repeat one that is already on that list.

STEP 3 — RESEARCH. Gather today's fintech news from the last 24 hours, in two
buckets:
  (a) SAUDI ARABIA — SAMA regulation and licensing, local banks, payments,
      Saudi fintech funding rounds, Vision 2030 financial-sector moves.
  (b) GLOBAL — anything materially important in payments, banking, crypto and
      tokenisation, embedded finance, or AI in financial services.
Prefer primary sources (regulator announcements, company statements, reputable
financial press). Use concrete figures and name the organisations. If a claim
cannot be sourced, leave it out rather than softening it.

STEP 4 — PRODUCT SEGMENT. Every episode must teach one fintech product or
product category the listener does not yet know, so that over time she builds
a map of what exists in the market. Pick ONE that is not already covered,
ideally connected to something in today's news. Explain, in plain language:
what the product actually does, what problem it solves, who the notable
providers are globally and in Saudi/GCC if any, how the money flows, and what
a bank or PSP has to do to offer it. This segment should take about 40 percent
of the character budget — it is the part she values most, so do not let the
news crowd it out.

STEP 5 — SCRIPT. Write a natural two-host conversation.

  HARD BUDGET: the finished spoken script must not exceed 5,000 CHARACTERS
  including spaces. Count the characters before generating any audio, and cut
  the script down if it is over. This is a spending limit, not a style note:
  ElevenLabs charges 1 credit per character, so the script length IS the bill.
  5,000 characters x 21.7 episodes is what the remaining allowance covers for
  a full month. Going over means the show runs dry before month end.
  That budget produces roughly 5 and a half minutes of audio.

Within that budget, aim for roughly 45 to 55 alternating turns:
  - LAYLA — anchors the episode, drives the running order, asks the questions
    a smart listener would ask.
  - SAMI — the analyst; explains mechanics, gives numbers, takes positions.
They should genuinely discuss rather than read: disagree where there is a real
disagreement, and let one push back on the other. No sound-effect directions,
no music cues, no "welcome back after the break" — plain spoken dialogue only.
Structure: brief cold open on the single biggest story, then Saudi news, then
global news, then the product segment, then a short close on what to watch
tomorrow.
The listener is a Saudi banking product manager working in merchant acquiring
and corporate onboarding. Assume she knows banking well; do not explain what a
POS terminal or an IBAN is. Do explain unfamiliar products properly.

STEP 6 — AUDIO. Generate the episode with ElevenLabs, v3 pipeline:
  - LAYLA -> voice "Lauren"
  - SAMI  -> voice "Nate"
Render the full conversation as a single continuous MP3. Do not re-generate
the audio to fix small wording issues — every regeneration costs the full
character count again.

STEP 7 — PUBLISH. Using the GitHub connector, commit the MP3 to the
repository sforaihey/fintech-pulse on branch main, into the incoming/ folder,
named exactly:
    incoming/Fintech Pulse Daily Ep. NN.mp3
(NN being the two-digit number from Step 1). Committing there is what
publishes the episode — an automation picks it up from that folder, so do not
edit feed.xml, episodes.json or the episodes/ folder yourself.
Also attach the MP3 to your reply as a backup copy.
If the commit fails, say so plainly in your reply and attach the MP3 — do not
retry the audio generation, the file is already made and paid for.

STEP 8 — LOG THE PRODUCT AND THE SPEND. In the same commit or a follow-up one:
  (a) Append one line to docs/products-covered.md:
      - Ep. NN (YYYY-MM-DD) — <product name>: <one-line description>
  (b) Append one row to docs/credit-log.md:
      | NN | YYYY-MM-DD | <characters> | <length m:ss> |
Be accurate about the character count — it is the only record of what the show
spends, and it is what stops it running out of credit unnoticed.

STEP 9 — REPORT. Reply with the episode number, its length, the character
count, the three main stories covered, and the product explained. Include the
show notes as text so they can be read later.
```

---

## If something goes wrong

- **No episode appeared** — check the run's reply first. A Step 0 stop on a
  Friday or Saturday is correct behaviour, not a failure.
- **The episode was made but the commit failed** — GitHub is probably not
  enabled on the task. The MP3 is attached to the run's reply; save it into
  ~/Desktop/Fintech podcast and your Mac will publish it.
- **The episode is in the feed but not on the phone** — Apple Podcasts
  refreshes on its own cycle; pull down to refresh on the show page.
