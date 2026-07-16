#!/usr/bin/env bash
# Clone the assignment's target repository into ./target-repo
set -euo pipefail
REPO_URL="${1:-https://github.com/codejsha/spring-rest-sakila}"
DEST="${2:-target-repo}"
if [ -d "$DEST" ]; then
  echo "Destination '$DEST' already exists; skipping clone."
else
  git clone --depth 1 "$REPO_URL" "$DEST"
fi
echo "Cloned to: $DEST"
