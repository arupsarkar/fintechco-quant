#!/usr/bin/env bash
# A/B token measurement: prose-spec vs metadata-spec generation.
# Runs headless (claude -p), captures usage JSON, gates on compliance.
# Usage: ./scripts/measure_generation.sh <arm-label>
set -euo pipefail
cd "$(dirname "$0")/.."
ARM="${1:?usage: measure_generation.sh <arm-label e.g. prose|metadata>}"

./setup_demo.sh > /dev/null                     # identical clean slate per trial

PROMPT="Using the fred-gateway data, analyze how Federal Reserve policy \
changes historically impact market volatility. Follow the shop standards."

# Headless run: full agentic loop, JSON result with usage + cost.
claude -p "$PROMPT" --output-format json > /tmp/gen_result.json

# Compliance gate: a cheap-but-broken generation is a FAILURE, not a saving.
if uv run python scripts/eval_regeneration.py > /tmp/eval_out.txt 2>&1; then
  VERDICT="PASS"
else
  VERDICT="FAIL"
fi

# Extract usage and append one measurement record.
python3 - "$ARM" "$VERDICT" <<'EOF'
import json, sys, datetime
arm, verdict = sys.argv[1], sys.argv[2]
r = json.load(open("/tmp/gen_result.json"))
rec = {
  "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "arm": arm,
  "verdict": verdict,
  "cost_usd": r.get("total_cost_usd"),
  "usage": r.get("usage"),
  "duration_ms": r.get("duration_ms"),
  "num_turns": r.get("num_turns"),
}
open("eval/token_log.jsonl", "a").write(json.dumps(rec) + "\n")
print(f"{arm}: {verdict} · cost=${rec['cost_usd']} · usage={rec['usage']}")
EOF