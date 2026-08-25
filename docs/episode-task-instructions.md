# Fintech Pulse — episode task

Paste the block below into a **new** claude.ai scheduled task (leave the
existing dashboard task alone).

- **Frequency:** Daily · 07:15 AM — *not* "Weekdays", which means Mon–Fri.
  The Sunday–Thursday rule is enforced inside the instructions instead.
- **Connectors:** the GitHub connector must be authorised, with access to
  `sforaihey/fintech-pulse`. Without it the episode cannot reach the feed.
- **Permissions:** "Automatically approve" is required for an unattended run.

Committing to `incoming/` triggers `.github/workflows/build-feed.yml`, which
tags the audio, adds it to `feed.xml` and clears the folder. Nothing on the
Mac is involved.

---

```
Produce today's episode of "Fintech Pulse Daily", a two-host audio briefing,
and publish it to the podcast feed.

STEP 0 — DAY CHECK. Work out today's day of the week in Riyadh (UTC+3). If it
is Friday or Saturday, STOP NOW and produce nothing at all: this show runs
Sunday to Thursday only. Do not generate audio, do not commit anything.

STEP 1 — EPISODE NUMBER. Read episodes.json from the GitHub repository
sforaihey/fintech-pulse (branch main). Take the highest episode number in it
and add 1. That is today's episode number, written with two digits (e.g. 03).
If the file cannot be read, STOP and report the failure rather than guessing a
number — a duplicate number overwrites an existing episode.

STEP 2 — WHAT ALREADY GOT COVERED. Read docs/products-covered.md from the same
repository. It lists the fintech products explained in previous episodes. You
must not repeat one that is already on that list.

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
a map of what exists in the market. Pick ONE that is not in
docs/products-covered.md, ideally connected to something in today's news.
Explain, in plain language: what the product actually does, what problem it
solves, who the notable providers are globally and in Saudi/GCC if any, how the
money flows, and what a bank or PSP has to do to offer it. This segment should
take about 40 percent of the character budget — it is the part she values
most, so do not let the news crowd it out.

STEP 5 — SCRIPT. Write a natural two-host conversation.

  HARD BUDGET: the finished spoken script must not exceed 5,800 CHARACTERS
  including spaces. Count the characters before generating any audio, and cut
  the script down if it is over. This is a spending limit, not a style note:
  ElevenLabs charges 1 credit per character, and the monthly allowance only
  covers about 5,900 characters per episode across a full month of weekdays.
  Going over means the show runs out of credit before month end.
  That budget produces roughly 6 to 7 minutes of audio.

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

STEP 7 — PUBLISH. Commit the MP3 to the GitHub repository
sforaihey/fintech-pulse on branch main, into the incoming/ folder, named
exactly:
    incoming/Fintech Pulse Daily Ep. NN.mp3
(NN being the two-digit number from Step 1). Committing there is what
publishes the episode — an automation picks it up from that folder, so do not
edit feed.xml, episodes.json or the episodes/ folder yourself.

STEP 8 — RECORD THE PRODUCT. In the same commit, append one line to
docs/products-covered.md:
    - Ep. NN (YYYY-MM-DD) — <product name>: <one-line description>

STEP 9 — REPORT. Reply with the episode number, its length, the three main
stories covered, and the product explained. Include the show notes as text so
they can be read later.
```

---

## If something goes wrong

- **No episode appeared** — check the run's reply first. A Step 0 stop on a
  Friday or Saturday is correct behaviour, not a failure.
- **The GitHub Action failed** — see the Actions tab of the repository. The
  usual cause is a filename without a recognisable episode number.
- **The episode is there but not on the phone** — Apple Podcasts refreshes on
  its own cycle; pull down to refresh on the show page.
