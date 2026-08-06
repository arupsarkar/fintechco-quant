---
name: fed-analysis
description: Execute the Fed policy volatility analysis per spec/analysis_spec.json with minimum iterations. Use whenever asked to perform/run/regenerate the Fed policy volatility analysis.
---

# Fed Analysis — Minimum-Iteration Recipe

Execute EXACTLY these steps, in order, with EXACTLY these tools.
No directory listing, no exploratory reads, no re-reading files
already in context, no intermediate test runs beyond the gates.

1. Read spec/analysis_spec.json          (tool: Read — once)
2. If analysis/fed_vix_impact.py exists AND matches the spec:
   skip to step 4. Do not rewrite compliant code.
3. Write analysis/fed_vix_impact.py per the spec's interface_contract
   and quality_gates                     (tool: Write — one file, once)
4. Run: uv run python analysis/fed_vix_impact.py   (tool: Bash — once)
5. Run: uv run python scripts/verify_golden.py     (tool: Bash — once)
6. Report: results summary + gate verdict. STOP. No further iteration
   unless a step FAILED — on failure, fix the specific failure only.

Known context (do not rediscover): cache holds FEDFUNDS.csv and
VIXCLS.csv in data/cache/ (date,value columns); golden lives at
data/seeds/golden_results.json (verification only); results keys per
golden.