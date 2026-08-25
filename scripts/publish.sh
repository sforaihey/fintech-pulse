#!/bin/bash
# Publish any new episodes sitting in ~/Desktop/Fintech podcast/ to the feed.
# Safe to run repeatedly: it exits quietly when there is nothing new.
set -euo pipefail

cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:$PATH"

python3 scripts/build_feed.py

if [ -z "$(git status --porcelain)" ]; then
  echo "nothing new to publish"
  exit 0
fi

git add -A
git -c user.name="Sawsan Alforaihey" -c user.email="s.foraihey@gmail.com" \
    commit -q -m "Publish episodes $(date '+%Y-%m-%d %H:%M')"
git push -q origin main
echo "published -> https://sforaihey.github.io/fintech-pulse/feed.xml"
