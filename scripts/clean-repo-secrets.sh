#!/usr/bin/env bash
# Remove sensitive or local-only files from Git tracking while keeping them on disk.
# Run from the repository root: ./scripts/clean-repo-secrets.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PATTERNS=(
  ".env"
  "backend/.env"
  "frontend/.env"
  "frontend/.env.local"
  ".env.local"
  "*.pem"
  "*.key"
  "credentials.json"
  "secrets.json"
)

echo "==> Checking for tracked sensitive files..."
FOUND=0
for pattern in "${PATTERNS[@]}"; do
  while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    echo "  tracked: $file"
    FOUND=1
  done < <(git ls-files -- "$pattern" 2>/dev/null || true)
done

if [[ "$FOUND" -eq 0 ]]; then
  echo "No sensitive files are currently tracked."
else
  echo
  echo "==> Removing sensitive files from Git index (files stay on disk)..."
  for pattern in "${PATTERNS[@]}"; do
    git ls-files -- "$pattern" 2>/dev/null | while IFS= read -r file; do
      [[ -z "$file" ]] && continue
      git rm --cached -- "$file"
      echo "  untracked: $file"
    done
  done
  echo
  echo "Review changes with: git status"
  echo "Commit with: git commit -m \"chore: stop tracking local env and secret files\""
fi

echo
echo "==> Verifying .gitignore covers common secret paths..."
REQUIRED=(
  ".env"
  "backend/.env"
  "frontend/.env"
  "frontend/.env.local"
)
for entry in "${REQUIRED[@]}"; do
  if grep -qxF "$entry" .gitignore; then
    echo "  ok: $entry"
  else
    echo "  missing from .gitignore: $entry"
  fi
done

echo
echo "Done. Push only after reviewing git status and commit."
