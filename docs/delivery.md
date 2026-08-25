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

## Fallback B — Notion bridge

If GitHub can never be enabled on the task, point Step 7 at the Notion page
"Fintech Pulse — Episode Drop" instead, and run:

    NOTION_TOKEN=... python3 scripts/pull_from_notion.py && ./scripts/publish.sh

`scripts/pull_from_notion.py` reads the drop page, downloads any episode the
feed does not already have, and puts it in `incoming/`. It needs a Notion
internal integration token (notion.so/my-integrations) with the drop page
shared to it. Create the token yourself and keep it out of the repo — either
in the shell environment on this Mac, or as a GitHub Actions secret named
`NOTION_TOKEN` if you want this running in the cloud.
