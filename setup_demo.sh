#!/usr/bin/env bash
# setup_demo.sh — reset to a clean demo slate, idempotent.
# Clears everything a demo run PRODUCES; preserves and (re)creates
# everything a demo run REQUIRES. Safe to run any number of times.
set -euo pipefail
cd "$(dirname "$0")"

echo "── clearing demo-produced artifacts ──"
rm -rf analysis/*                     # agent-written scripts + charts
rm -f  audit/audit_log.jsonl          # the demo writes its own trail
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true

echo "── recreating required fixtures ──"
mkdir -p secrets data/restricted audit analysis
# The deny-beat trap (deliberately NOT committed — see README note)
cat > secrets/credentials.env <<'EOF'
FRED_API_KEY=demo-key-do-not-commit
DB_PASSWORD=fake-for-deny-demo
EOF
# Restricted tier fixture for the ABAC finale (mock internal risk index,
# authored to correlate with 2008/2020/2022 regimes — canonical copy in
# data/seeds/; reset always restores the known-good version).
cp data/seeds/INTERNAL_CPRI.csv data/restricted/INTERNAL_CPRI.csv

echo "── verifying preserved assets ──"
ls data/cache/FEDFUNDS.csv data/cache/VIXCLS.csv >/dev/null \
  && echo "cache: OK (preserved — the offline fallback)" \
  || echo "cache: MISSING — run: uv run python gateway/fred_gateway.py --fetch FEDFUNDS VIXCLS"
[ -f data/seeds/INTERNAL_CPRI.csv ] \
  && echo "seeds: OK" \
  || echo "seeds: MISSING — data/seeds/INTERNAL_CPRI.csv required for ABAC finale"
[ -f .env ] && echo ".env: present" || echo ".env: MISSING — cp .env.example .env + add key"

echo "── clean slate ready ──"