#!/usr/bin/env bash
# Token A/B: requirements-in-prompt (Arm A) vs. rulebook+short-prompt (Arm B).
# Each trial: clean slate -> headless generation -> compliance gate -> usage logged.
# The metric is tokens/cost per COMPLIANT generation. Run K>=3 per arm.
# Usage: ./scripts/measure_generation.sh prose | metadata
set -euo pipefail
cd "$(dirname "$0")/.."
ARM="${1:?usage: measure_generation.sh prose|metadata}"

PROMPT_PROSE="Using the fred-gateway data, analyze how Federal Reserve policy \
changes historically impact market volatility. Requirements: events are \
month-over-month FEDFUNDS changes of at least 25 basis points, classified as \
hikes or cuts; measure mean VIX in windows of 30 trading days before and after \
each event; run a significance test per group and state N everywhere; include \
data provenance, sanity checks with one hand-recomputed event, and an \
assumptions-and-limitations section; write analysis/fed_vix_impact.py exposing \
load_csv, identify_events, build_windows, t_test_paired, DATA_DIR; persist key \
results to analysis/results.json. Data only via the fred-gateway cache."

PROMPT_METADATA="Perform the Fed policy volatility analysis per the spec."

if [ "$ARM" = "prose" ]; then PROMPT="$PROMPT_PROSE"; else PROMPT="$PROMPT_METADATA"; fi

./setup_demo.sh > /dev/null
rm -f analysis/fed_vix_impact.py analysis/results.json   # force true regeneration

claude -p "$PROMPT" --permission-mode acceptEdits --output-format json > /tmp/gen_result.json

if uv run python scripts/eval_regeneration.py --log > /tmp/eval_out.txt 2>&1; then
  VERDICT="PASS"; else VERDICT="FAIL"; fi

python3 - "$ARM" "$VERDICT" <<'EOF'
import json, sys, datetime
arm, verdict = sys.argv[1], sys.argv[2]
r = json.load(open("/tmp/gen_result.json"))
u = r.get("usage") or {}
rec = {
  "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "arm": arm, "verdict": verdict,
  "cost_usd": r.get("total_cost_usd"),
  "input_tokens": u.get("input_tokens"),
  "output_tokens": u.get("output_tokens"),
  "cache_read": u.get("cache_read_input_tokens"),
  "cache_write": u.get("cache_creation_input_tokens"),
  "num_turns": r.get("num_turns"),
  "duration_ms": r.get("duration_ms"),
}
open("eval/token_log.jsonl","a").write(json.dumps(rec)+"\n")
print(f"{arm}: {verdict} · ${rec['cost_usd']} · in={rec['input_tokens']} out={rec['output_tokens']} turns={rec['num_turns']}")
EOF