#!/usr/bin/env bash
# Fetch CloudWatch logs for the backend and/or ingestion Lambda.
#
# Usage:
#   ./fetch-lambda.sh [backend|ingestion|all] [options]
#
# Target (positional, default: all):
#   backend      plugandplay-support  (FastAPI/chat)
#   ingestion    plugandplay-doc-ingestion  (SQS document worker)
#   all          both
#
# Options:
#   --since <dur>   How far back to read (default 1h). e.g. 30m, 2h, 1d,
#                   or an absolute time like 2026-07-14T09:00:00.
#   --errors        Only events matching the error pattern ($ERROR_PATTERN).
#   --follow        Stream new events live (single target only; Ctrl-C stops).
#   --format <fmt>  aws logs tail format: short | detailed | json (default short).
#   --save          Also write output to logs/out/<timestamp>/<fn>[.errors].log
#   -h, --help      Show this help.
#
# Needs AWS CLI v2 (`aws logs tail`) authenticated for the account/region.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

target="all"
SINCE="1h"
FORMAT="short"
ERRORS=0
FOLLOW=0
SAVE=0

# First non-flag arg is the target.
if [[ $# -gt 0 && "${1:0:1}" != "-" ]]; then target="$1"; shift; fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)  SINCE="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    --errors) ERRORS=1; shift ;;
    --follow) FOLLOW=1; shift ;;
    --save)   SAVE=1; shift ;;
    -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,"");print;next}{exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

need aws "install AWS CLI v2 and run 'aws configure'."

case "$target" in
  backend)   fns=("$BACKEND_LAMBDA") ;;
  ingestion) fns=("$INGESTION_LAMBDA") ;;
  all)       fns=("$BACKEND_LAMBDA" "$INGESTION_LAMBDA") ;;
  *) echo "unknown target '$target' (want: backend | ingestion | all)" >&2; exit 2 ;;
esac

if [[ $FOLLOW -eq 1 && ${#fns[@]} -gt 1 ]]; then
  echo "error: --follow streams one function at a time; pick 'backend' or 'ingestion'." >&2
  exit 2
fi

RD=""
if [[ $SAVE -eq 1 ]]; then RD="$(run_dir)"; mkdir -p "$RD"; fi

for fn in "${fns[@]}"; do
  group="/aws/lambda/$fn"
  lbl=""; [[ $ERRORS -eq 1 ]] && lbl=", errors-only"
  echo "==> $group  (region=$AWS_REGION, since=$SINCE$lbl)" >&2

  args=(logs tail "$group" --region "$AWS_REGION" --since "$SINCE" --format "$FORMAT")
  [[ $FOLLOW -eq 1 ]] && args+=(--follow)
  [[ $ERRORS -eq 1 ]] && args+=(--filter-pattern "$ERROR_PATTERN")

  if [[ $SAVE -eq 1 ]]; then
    suffix=""; [[ $ERRORS -eq 1 ]] && suffix=".errors"
    out="$RD/${fn}${suffix}.log"
    aws "${args[@]}" | tee "$out"
    echo "    saved -> $out" >&2
  else
    aws "${args[@]}"
  fi
done
