"""Append the episode's product and character spend to the two logs."""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EPISODE = REPO / "episode.json"

if not EPISODE.exists():
    raise SystemExit("no episode.json — nothing to log")

ep = json.loads(EPISODE.read_text())
number, date = f"{ep['number']:02d}", ep["date"]

products = REPO / "docs" / "products-covered.md"
text = products.read_text().rstrip("\n")
if f"Ep. {number}" not in text:
    note = ep.get("product_note") or ep.get("product", "")
    products.write_text(f"{text}\n- Ep. {number} ({date}) — {ep['product']}: {note}\n")
    print(f"logged product: {ep['product']}")

log = REPO / "docs" / "credit-log.md"
text = log.read_text().rstrip("\n")
if f"| {number} |" not in text:
    log.write_text(f"{text}\n| {number} | {date} | {ep['characters']} | — |\n")
    print(f"logged spend: {ep['characters']:,} characters")

notes = REPO / "docs" / "notes" / f"ep{number}.md"
notes.parent.mkdir(exist_ok=True)
notes.write_text(f"# Ep. {number} — {date}\n\n{ep.get('notes', '')}\n")
print(f"wrote {notes.relative_to(REPO)}")
