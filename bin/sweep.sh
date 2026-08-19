#!/usr/bin/env bash
# sweep.sh — Phase 1. Ranked vocabulary sweep. Requires ripgrep.
#
# Usage:  ./sweep.sh terms.txt [path ...]
#
# terms.txt: one term per line. '#' comments and blank lines ignored.
#            Prefix a term with '~' for substring matching (no word boundary).
#
# Outputs:  .agent/sweep-ranked.txt   files ranked by hit count
#           .agent/findings.md        every hit with file:line and the matching line
#
# Read the top 3 files from sweep-ranked.txt, extract the project's REAL
# identifiers, then re-run this script with those. Two rounds, always.

set -uo pipefail

command -v rg >/dev/null 2>&1 || { echo "ripgrep (rg) not found. Install: https://github.com/BurntSushi/ripgrep" >&2; exit 1; }

TERMS_FILE="${1:-}"
[ -f "$TERMS_FILE" ] || { echo "usage: $0 terms.txt [path ...]" >&2; exit 1; }
shift
PATHS=("$@")
[ ${#PATHS[@]} -eq 0 ] && PATHS=(".")

mkdir -p .agent
RANKED=".agent/sweep-ranked.txt"
FILES=".agent/sweep-files.txt"
FINDINGS=".agent/findings.md"

WORD_TERMS=()
SUB_TERMS=()
while IFS= read -r line; do
  line="${line%%#*}"
  line="$(echo "$line" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$line" ] && continue
  case "$line" in
    '~'*) SUB_TERMS+=("${line#\~}") ;;
    *)    WORD_TERMS+=("$line") ;;
  esac
done < "$TERMS_FILE"

[ ${#WORD_TERMS[@]} -eq 0 ] && [ ${#SUB_TERMS[@]} -eq 0 ] && { echo "no terms in $TERMS_FILE" >&2; exit 1; }

RG_COMMON=(--hidden --no-messages
           --glob '!node_modules' --glob '!.git' --glob '!dist' --glob '!build'
           --glob '!out' --glob '!coverage' --glob '!*.min.*' --glob '!*.map'
           --glob '!.venv' --glob '!__pycache__' --glob '!target'
           --max-columns 200)

build_args() {
  local mode="$1"; shift
  local -a args=()
  if [ "$mode" = word ]; then args+=(-w); fi
  for t in "$@"; do args+=(-e "$t"); done
  printf '%s\n' "${args[@]}"
}

# ---- ranked counts -------------------------------------------------------
: > "$RANKED.tmp"
if [ ${#WORD_TERMS[@]} -gt 0 ]; then
  mapfile -t A < <(build_args word "${WORD_TERMS[@]}")
  rg -ic "${A[@]}" "${RG_COMMON[@]}" "${PATHS[@]}" >> "$RANKED.tmp" 2>/dev/null
fi
if [ ${#SUB_TERMS[@]} -gt 0 ]; then
  mapfile -t B < <(build_args sub "${SUB_TERMS[@]}")
  rg -ic "${B[@]}" "${RG_COMMON[@]}" "${PATHS[@]}" >> "$RANKED.tmp" 2>/dev/null
fi

awk -F: '{c[substr($0,1,length($0)-length($NF)-1)] += $NF} END {for (f in c) printf "%6d  %s\n", c[f], f}' \
  "$RANKED.tmp" | sort -rn > "$RANKED"
rm -f "$RANKED.tmp"
awk '{ $1=""; sub(/^ +/,""); print }' "$RANKED" > "$FILES"

# ---- detailed findings ---------------------------------------------------
{
  echo "# Findings"
  echo
  echo "_Generated $(date -u '+%Y-%m-%d %H:%M UTC') from \`$TERMS_FILE\`_"
  echo
  echo "Classification rule: a hit counts only if it sits inside a control-flow guard"
  echo "(\`if\`, \`&&\`, \`?:\`, \`?.\`, early return) or a configuration collection."
  echo "String literals, comments, and formatting expressions do not count."
  echo
  echo "| ok? | file:line | match |"
  echo "|---|---|---|"
  {
    [ ${#WORD_TERMS[@]} -gt 0 ] && rg -in -w "${A[@]}" "${RG_COMMON[@]}" "${PATHS[@]}" 2>/dev/null
    [ ${#SUB_TERMS[@]} -gt 0 ] && rg -in "${B[@]}" "${RG_COMMON[@]}" "${PATHS[@]}" 2>/dev/null
  } | sort -u | while IFS= read -r hit; do
      loc="${hit%%:*}"; rest="${hit#*:}"
      lineno="${rest%%:*}"; text="${rest#*:}"
      text="$(echo "$text" | sed 's/^[[:space:]]*//' | cut -c1-110 | sed 's/|/\\|/g')"
      echo "| [ ] | \`$loc:$lineno\` | \`$text\` |"
    done
} > "$FINDINGS"

echo "wrote $RANKED"
echo "wrote $FILES"
echo "wrote $FINDINGS"
echo
echo "--- top files ---"
head -15 "$RANKED"
echo
echo "NEXT: open the top 3 files, extract the project's real identifiers,"
echo "      put them in a new terms file, and run this again."
