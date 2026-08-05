# FinTechCo Engineering Standards — Quantitative Analysis

You are working in a FinTechCo-governed environment. These standards are policy, not suggestions.

## Data governance
1. All market/economic data enters ONLY through the fred-gateway MCP tools. Never fetch financial data via raw HTTP, curl, or ad-hoc
   scripts — the gateway is the audited door.
2. Every analysis must state its data provenance: series IDs, source, date range, and retrieval time.
3. Data under data/restricted/ is classified. Do not read, copy, or
   summarize it unless the task context explicitly grants the
   entitlement.

## Analysis integrity
4. Every quantitative claim ships with a sanity check: verify date
   alignment, spot-check at least one computed value by hand-method, and state N.
5. Every deliverable includes an ASSUMPTIONS & LIMITATIONS section.
   Correlation is not causation; say so where relevant.
6. Analysis must persist key results to analysis/results.json
   (keys per data/seeds/golden_results.json) — regenerated code must
   reproduce the golden numbers.   
7. Prefer plan-then-execute for any new analysis: propose the
   approach before writing code.

## Security
8. Never read, print, or commit anything under secrets/ or any file
   matching *.key, *.pem, .env*.
9. Never run destructive commands (rm -rf, force push, DROP).
10. All outputs are role-aware: deliverables render through the role
   context provided, never bypassing it.