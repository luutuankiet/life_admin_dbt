#!/usr/bin/env bash
#
# Generate a repo's documentation index from the frontmatter on each page.
#
#   gen-docs-index.sh [--repo DIR]            write every index
#   gen-docs-index.sh [--repo DIR] --check    exit 1 if any index is stale
#
# One source of truth -- the frontmatter -- and up to three renders:
#
#   docs/README.md                              all five collections, for humans
#   .claude/skills/codebase-map/SKILL.md        where things live: architecture, guides
#   .claude/skills/repo-maintenance/SKILL.md    what breaks: traps, reference, decisions
#
# Each render is the block between the two marker comments; everything outside
# them is hand-written and survives. A skill target that does not exist is
# skipped rather than created -- authoring the body is a human's job, and
# whether it exists at all is check 5 of audit.sh.
#
# Never hand-maintain an index. A hand-written one silently orphans pages: the
# page still exists, nothing links to it, and nobody notices for a year.
#
# Dependency-free bash + awk on purpose -- a repo laid out this way may have no
# runtime at all, and reaching for a static site generator to render one list
# would be absurd.

set -euo pipefail

REPO=""
MODE=write

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)  REPO="$2"; shift 2 ;;
    --check) MODE=check; shift ;;
    "")      shift ;;
    *)       echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
REPO="$(cd -- "$REPO" && pwd)"
DOCS="$REPO/docs"

BEGIN_MARK="<!-- BEGIN GENERATED INDEX -- edit the pages, not this block -->"
END_MARK="<!-- END GENERATED INDEX -->"

# ---------------------------------------------------------------- helpers ---

# fm <file> <key> -- read one flat `key: value` out of the leading `---` block.
fm() {
  awk -v key="$2" '
    NR == 1 && $0 != "---" { exit }
    NR == 1                { next }
    $0 == "---"            { exit }
    {
      i = index($0, ":"); if (i == 0) next
      k = substr($0, 1, i - 1); v = substr($0, i + 1)
      gsub(/^[ \t]+|[ \t]+$/, "", k)
      gsub(/^[ \t]+|[ \t]+$/, "", v)
      sub(/^"/, "", v); sub(/"$/, "", v)
      if (k == key) { print v; exit }
    }
  ' "$1"
}

# heading <file> -- the first `# ` line, for pages that carry no frontmatter.
heading() { awk '/^# / { sub(/^# +/, ""); print; exit }' "$1"; }

# cell <text> -- make a string safe inside a markdown table cell.
cell() { printf '%s' "${1//|/\\|}"; }

# pages <dir> -- sorted page paths, or nothing at all if the directory is empty.
pages() {
  [ -d "$DOCS/$1" ] || return 0
  find "$DOCS/$1" -maxdepth 1 -name '*.md' ! -name 'README.md' | LC_ALL=C sort
}

# guides -- long-form pages that sit at the top level of docs/ rather than in a
# collection directory. Without this collection they are orphans: live, linked
# from nothing, and invisible to the one index everything else routes through.
#
# A top-level page with no `title:` is NOT silently claimed here. It would index
# as a blank row, which reads as clean and is worse than absent. It is an orphan,
# and reporting it is check 6 of audit.sh, not this generator's job.
guides() {
  local f
  [ -d "$DOCS" ] || return 0
  find "$DOCS" -maxdepth 1 -name '*.md' ! -name 'README.md' | LC_ALL=C sort |
  while IFS= read -r f; do
    [ -n "$(fm "$f" title)" ] && printf '%s\n' "$f"
  done
  return 0
}

# ---------------------------------------------------------------- sections ---
# Each takes a path prefix, because the two skill bodies sit three levels down
# from docs/ while docs/README.md sits inside it.

sec_architecture() {
  local p="$1" f n=0
  printf '\n## Where things live\n\n'
  printf 'One page per area of the system. Read before going looking for where\n'
  printf 'something is implemented.\n\n'
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if [ "$n" -eq 0 ]; then printf '| page | covers | verified |\n|---|---|---|\n'; fi
    n=$((n + 1))
    printf '| [%s](%sarchitecture/%s) | %s | %s |\n' \
      "$(cell "$(fm "$f" title)")" "$p" "$(basename -- "$f")" \
      "$(cell "$(fm "$f" covers)")" "$(fm "$f" verified)"
  done <<EOF
$(pages architecture)
EOF
  if [ "$n" -eq 0 ]; then printf '_No pages yet._\n'; fi
}

sec_traps() {
  local p="$1" f n=0
  printf '\n## Traps\n\n'
  printf 'Failure modes that produce no error message, indexed by the symptom you\n'
  printf 'would observe. Read before debugging behaviour that is wrong but not\n'
  printf 'crashing.\n\n'
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if [ "$n" -eq 0 ]; then printf '| symptom | page | area | verified |\n|---|---|---|---|\n'; fi
    n=$((n + 1))
    printf '| %s | [%s](%straps/%s) | %s | %s |\n' \
      "$(cell "$(fm "$f" symptom)")" "$(basename -- "$f" .md)" "$p" "$(basename -- "$f")" \
      "$(cell "$(fm "$f" area)")" "$(fm "$f" verified)"
  done <<EOF
$(pages traps)
EOF
  if [ "$n" -eq 0 ]; then printf '_No pages yet._\n'; fi
}

sec_reference() {
  local p="$1" f n=0
  printf '\n## Reference\n\n'
  printf 'Simply true, and expensive to re-derive.\n\n'
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if [ "$n" -eq 0 ]; then printf '| page | summary | verified |\n|---|---|---|\n'; fi
    n=$((n + 1))
    printf '| [%s](%sreference/%s) | %s | %s |\n' \
      "$(cell "$(fm "$f" title)")" "$p" "$(basename -- "$f")" \
      "$(cell "$(fm "$f" summary)")" "$(fm "$f" verified)"
  done <<EOF
$(pages reference)
EOF
  if [ "$n" -eq 0 ]; then printf '_No pages yet._\n'; fi
}

# A repo with no top-level guide gets no heading at all. Every other collection
# is a directory that was scaffolded deliberately; this one is a file pattern,
# and an empty heading for a pattern is noise rather than an invitation.
sec_guides() {
  local p="$1" f n=0 body=""
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n=$((n + 1))
    body="$body$(printf '| [%s](%s%s) | %s | %s |' \
      "$(cell "$(fm "$f" title)")" "$p" "$(basename -- "$f")" \
      "$(cell "$(fm "$f" summary)")" "$(fm "$f" verified)")
"
  done <<EOF
$(guides)
EOF
  [ "$n" -eq 0 ] && return 0
  printf '\n## Guides\n\n'
  printf 'Long-form pages that belong to no single area.\n\n'
  printf '| page | summary | verified |\n|---|---|---|\n'
  printf '%s' "$body"
}

sec_decisions() {
  local p="$1" f n=0
  printf '\n## Decisions\n\n'
  printf 'Why the repo is the way it is. A merged decision is immutable -- supersede\n'
  printf 'it with a new one rather than editing it.\n\n'
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    n=$((n + 1))
    printf -- '- [%s](%sadr/%s)\n' "$(cell "$(heading "$f")")" "$p" "$(basename -- "$f")"
  done <<EOF
$(pages adr)
EOF
  if [ "$n" -eq 0 ]; then printf '_No decisions recorded yet._\n'; fi
}

# ----------------------------------------------------------------- renders ---

render_readme() {
  printf '%s\n' "$BEGIN_MARK"
  sec_architecture ""
  sec_traps ""
  sec_reference ""
  sec_guides ""
  sec_decisions ""
  printf '\n%s\n' "$END_MARK"
}

render_map() {
  printf '%s\n' "$BEGIN_MARK"
  sec_architecture "../../../docs/"
  sec_guides "../../../docs/"
  printf '\n%s\n' "$END_MARK"
}

render_maintenance() {
  printf '%s\n' "$BEGIN_MARK"
  sec_traps "../../../docs/"
  sec_reference "../../../docs/"
  sec_decisions "../../../docs/"
  printf '\n%s\n' "$END_MARK"
}

# -------------------------------------------------------------- the splice ---

STALE=0

# splice <file> <render-fn> -- replace the marked block, or report it stale.
splice() {
  local target="$1" fn="$2" rel="${1#"$REPO"/}"
  local tmp_block tmp_out

  grep -Fq "$BEGIN_MARK" "$target" || {
    echo "FAIL  begin marker missing from $rel" >&2; STALE=1; return 0; }
  grep -Fq "$END_MARK" "$target" || {
    echo "FAIL  end marker missing from $rel" >&2; STALE=1; return 0; }

  tmp_block=$(mktemp); tmp_out=$(mktemp)
  "$fn" > "$tmp_block"

  awk -v begin="$BEGIN_MARK" -v end="$END_MARK" -v block="$tmp_block" '
    index($0, begin) == 1 { while ((getline line < block) > 0) print line; skip = 1; next }
    index($0, end)   == 1 { skip = 0; next }
    !skip
  ' "$target" > "$tmp_out"

  if cmp -s "$tmp_out" "$target"; then
    echo "ok    $rel"
  elif [ "$MODE" = check ]; then
    echo "FAIL  $rel is stale -- run gen-docs-index.sh" >&2
    diff -u "$target" "$tmp_out" | sed 's/^/      /' >&2 || true
    STALE=1
  else
    cat -- "$tmp_out" > "$target"
    echo "ok    wrote $rel"
  fi

  rm -f -- "$tmp_block" "$tmp_out"
}

# ------------------------------------------------------------------- main ----

INDEX="$DOCS/README.md"
if [ ! -f "$INDEX" ]; then
  if [ "$MODE" = check ]; then
    echo "FAIL  $INDEX does not exist" >&2
    exit 1
  fi
  mkdir -p -- "$DOCS"
  { printf '# Documentation\n\n'
    printf 'Every page here is written for a maintainer six months from now who opened\n'
    printf 'exactly this file from a search result and has nothing else loaded.\n\n'
    printf 'This index is generated. Run `scripts/gen-docs-index.sh` after adding or\n'
    printf 'renaming a page; `--check` fails if it is stale.\n\n'
    printf '%s\n%s\n' "$BEGIN_MARK" "$END_MARK"
  } > "$INDEX"
fi

splice "$INDEX" render_readme

MAP="$REPO/.claude/skills/codebase-map/SKILL.md"
[ -f "$MAP" ] && splice "$MAP" render_map

MAINT="$REPO/.claude/skills/repo-maintenance/SKILL.md"
[ -f "$MAINT" ] && splice "$MAINT" render_maintenance

exit "$STALE"
