#!/usr/bin/env bash
# Remove sensitive or local-only files from Git tracking, and (optionally)
# prepare / run git history rewrite to purge known leaked API keys.
#
# Run from the repository root:
#   ./scripts/clean-repo-secrets.sh              # Section A: untrack only
#   ./scripts/clean-repo-secrets.sh --dry-run-rewrite   # Section B: show rewrite plan
#   ./scripts/clean-repo-secrets.sh --rewrite-history   # Section B: EXECUTE rewrite (team coordination required)
#
# WARNING: --rewrite-history rewrites git history and will require force-push.
# Do not run on a shared remote without coordinating with all collaborators.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="untrack"
for arg in "$@"; do
  case "$arg" in
    --dry-run-rewrite) MODE="dry-run-rewrite" ;;
    --rewrite-history) MODE="rewrite-history" ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--dry-run-rewrite|--rewrite-history]" >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Section A: untrack sensitive files (keep on disk)
# ---------------------------------------------------------------------------
section_a_untrack() {
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

  echo "==> [A] Checking for tracked sensitive files..."
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
    echo "==> [A] Removing sensitive files from Git index (files stay on disk)..."
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
  echo "==> [A] Verifying .gitignore covers common secret paths..."
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
}

# ---------------------------------------------------------------------------
# Section B: history rewrite for known leaked keys (git-filter-repo)
# ---------------------------------------------------------------------------
# Known leaked secrets (full strings used only as rewrite match targets).
# These must stay in this script so operators can scrub history; they are
# already public in prior commits. Prefer rotating keys in vendor panels first.
OPENROUTER_LEAKED='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'
GAPGPT_LEAKED='sk-gpqe35rzLyMYQVdNHLe3wE2Ij2oemOjttixApzORZPJBEnpa'

require_filter_repo() {
  if command -v git-filter-repo >/dev/null 2>&1; then
    return 0
  fi
  echo "ERROR: git-filter-repo is not installed." >&2
  echo "Install with one of:" >&2
  echo "  pip install git-filter-repo" >&2
  echo "  brew install git-filter-repo" >&2
  echo "BFG Repo-Cleaner is an alternative but is not wired into this script." >&2
  return 1
}

section_b_rewrite() {
  local execute="${1:-false}"

  echo
  echo "==> [B] History rewrite for leaked OpenRouter / GapGPT keys"
  echo "    Commits of interest (non-exhaustive):"
  echo "      OpenRouter: 49fe475, 09d8970"
  echo "      GapGPT:     add0033 (MIGRATION.md)"
  echo

  if ! require_filter_repo; then
    exit 1
  fi

  REPLACEMENTS_FILE="$(mktemp)"
  cleanup() { rm -f "$REPLACEMENTS_FILE"; }
  trap cleanup EXIT

  # git-filter-repo --replace-text format: literal==>replacement
  {
    printf '%s==><OPENROUTER_API_KEY>\n' "$OPENROUTER_LEAKED"
    printf '%s==><GAPGPT_API_KEY>\n' "$GAPGPT_LEAKED"
  } >"$REPLACEMENTS_FILE"

  echo "Replacement rules written to temp file:"
  sed 's/sk-[^=]*/sk-***REDACTED***/' "$REPLACEMENTS_FILE" || true
  echo

  local cmd=(git filter-repo --force --replace-text "$REPLACEMENTS_FILE")

  if [[ "$execute" != "true" ]]; then
    echo "DRY-RUN: would execute:"
    echo "  ${cmd[*]}"
    echo
    echo "This does NOT rewrite history yet."
    echo "After team coordination and key rotation, re-run with:"
    echo "  ./scripts/clean-repo-secrets.sh --rewrite-history"
    echo
    echo "After a successful rewrite you must force-push and have all"
    echo "collaborators re-clone or reset. See SECURITY_INCIDENT.md."
    return 0
  fi

  echo "EXECUTING history rewrite (irreversible without backups)..."
  echo "Ensure you have coordinated with all collaborators and rotated keys."
  "${cmd[@]}"
  echo
  echo "Rewrite complete. Next steps:"
  echo "  1. Inspect: git log --all -S 'sk-or-v1' -S 'sk-gp'"
  echo "  2. Force-push rewritten branches (team-approved only)."
  echo "  3. Notify collaborators to re-clone."
}

section_a_untrack

case "$MODE" in
  untrack)
    echo
    echo "Tip: run with --dry-run-rewrite to preview history scrub commands."
    echo "Done. Push only after reviewing git status and commit."
    ;;
  dry-run-rewrite)
    section_b_rewrite false
    ;;
  rewrite-history)
    section_b_rewrite true
    ;;
esac
