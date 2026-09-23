#!/bin/bash
# Run every Emmet benchmark case, one case at one size per Sublime call, and merge
# the results into one JSON file.
#
# Usage: tests/benchmarks/run_all.sh <st-run.sh> <out.json> [extra bench args...]
#   e.g. run_all.sh "$SCRATCH/tools/st-run.sh" after.json
#        run_all.sh "$SCRATCH/tools/st-run.sh" dry.json --runs 1 --warmup 1
# Env: CASES="type_first:small,10k ..." to run a subset.
set -u
RUN="$1"; OUT="$2"; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

: "${CASES:=load:- type_first:small,10k,100k type_first_css:10k type_first_jsx:10k
type_first_python:10k type_second:small,10k,100k type_in_tag:small,10k,100k
move:small,10k,100k move_python:10k move_in_abbr:small,10k completions:small,10k,100k
tab_context:small,10k,100k activated:small,10k tag_preview_text:small,10k,100k
tag_preview_close:small,10k,100k cmd_expand:small,10k,100k cmd_expand_css:10k
cmd_balance:small,10k,100k cmd_tag_pair:small,10k,100k cmd_rename:small,10k
reference:10k}"

status=0
for spec in $CASES; do
  case_name="${spec%%:*}"
  IFS=, read -ra sizes <<< "${spec#*:}"
  for size in "${sizes[@]}"; do
    piece="$TMP/$case_name-$size.json"
    if ! "$RUN" "$HERE/bench_emmet.py" --timeout 180 -- --case "$case_name" --size "$size" \
        --out "$piece" "$@" > "$TMP/log" 2>&1; then
      echo "FAILED $case_name $size"; tail -5 "$TMP/log"; status=1; continue
    fi
    grep -E 'median|retained|^RUN' "$TMP/log" | sed 's/^/  /'
  done
done

python3 - "$OUT" "$TMP" <<'PY'
import glob, json, sys
out, tmp = sys.argv[1], sys.argv[2]
meta, results = None, []
for f in sorted(glob.glob(f"{tmp}/*.json")):
    d = json.load(open(f))
    meta = meta or d["meta"]
    results += d["results"]
json.dump({"meta": meta, "results": results}, open(out, "w"), indent=2)
print(f"merged {len(results)} results -> {out}")
PY
exit $status
