#!/usr/bin/env bash
# verify-absence.sh — Phase 3. The lexical oracle.
#
# Usage:  ./verify-absence.sh terms.txt [allowlist.txt] [path ...]
#
# Exits 0 if no term appears anywhere outside the allowlist.
# Exits 1 and prints every remaining hit otherwise.
#
# allowlist.txt: one substring per line; any hit whose file:line contains it is ignored.
#                Use for tests, changelogs, and deliberately-kept references.
#
# This proves LEXICAL completeness only. It does not prove semantic completeness —
# dynamic dispatch, string-constructed calls, and DI wiring are invisible to it.
# Pair it with a runtime check (see FRAMEWORK §7).

set -uo pipefail

command -v rg >/dev/null 2>&1 || { echo "ripgrep (rg) not found." >&2; exit 2; }

TERMS_FILE="${1:-}"
[ -f "$TERMS_FILE" ] || { echo "usage: $0 terms.txt [allowlist.txt] [path ...]" >&2; exit 2; }
shift

ALLOW=""
if [ $# -gt 0 ] && [ -f "${1:-}" ]; then ALLOW="$1"; shift; fi
PATHS=("$@"); [ ${#PATHS[@]} -eq 0 ] && PATHS=(".")

TERMS=()
while IFS= read -r line; do
  line="${line%%#*}"
  line="$(echo "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$line" ] && continue
  TERMS+=("${line#\~}")
done < "$TERMS_FILE"
[ ${#TERMS[@]} -eq 0 ] && { echo "no terms in $TERMS_FILE" >&2; exit 2; }

ARGS=()
for t in "${TERMS[@]}"; do ARGS+=(-e "$t"); done

HITS=$(rg -in "${ARGS[@]}" \
  --hidden --no-messages \
  --glob '!node_modules' --glob '!.git' --glob '!dist' --glob '!build' \
  --glob '!out' --glob '!coverage' --glob '!*.min.*' --glob '!*.map' \
  --glob '!.agent' --glob '!.venv' --glob '!__pycache__' --glob '!target' \
  --max-columns 200 \
  "${PATHS[@]}" 2>/dev/null || true)

if [ -n "$ALLOW" ] && [ -n "$HITS" ]; then
  HITS=$(echo "$HITS" | grep -vF -f <(grep -v '^[[:space:]]*#' "$ALLOW" | sed '/^[[:space:]]*$/d') || true)
fi

if [ -z "$HITS" ]; then
  echo "PASS — no remaining references to ${#TERMS[@]} term(s)."
  exit 0
fi

COUNT=$(echo "$HITS" | wc -l | tr -d ' ')
echo "FAIL — $COUNT remaining reference(s):"
echo
echo "$HITS"
exit 1
