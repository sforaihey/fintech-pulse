# How an episode reaches the phone

The scheduled task runs in Anthropic's cloud and cannot touch this Mac, so the
episode has to travel through something both sides can reach.

## Primary route — GitHub (no Mac needed)

Task commits the MP3 to `incoming/` → `.github/workflows/build-feed.yml` tags
it, adds it to `feed.xml`, clears `incoming/` → GitHub Pages redeploys →
Apple Podcasts picks it up.

Requires the **GitHub connector enabled on the task itself**. Connectors on
claude.ai are per conversation, so having GitHub connected to the account is
not sufficient — it must be switched on for that task.

Tested end to end on 2026-08-25: an uploaded file was adopted, tagged, added
to the feed and the folder cleared, with this Mac doing nothing.

## Fallback A — save it by hand

Every run attaches the MP3 to its reply. Save it into `~/Desktop/Fintech
podcast` and the LaunchAgent publishes it within seconds. Needs the Mac awake.

# Watching the credit balance

`python3 scripts/credit_report.py` reports what is left and what episode
length that sustains, counting only Sunday-to-Thursday days remaining before
the plan renews.

By default it uses a figure typed in by hand from the usage page. To make it
live instead, create a key in the ElevenLabs developer portal (API Keys tab)
and put it in your shell profile:

    export ELEVENLABS_API_KEY="..."

The script then calls `GET /v1/user/subscription`, which returns the exact
`character_count`, `character_limit` and reset date — no more hand-editing,
and no chance of the figure going stale.

Keep the key in your environment or your password manager. It does not belong
in this repo, in the scheduled task's instructions, or in a chat message.
