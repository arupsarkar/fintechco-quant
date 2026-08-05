# FinTechCo Quant — Governed Agentic Analysis with Claude Code

A demonstration built for the FinTechCo scenario: an urgent quantitative
question answered in minutes by Claude Code — **under governance from the
developer's first keystroke to the executive's dashboard.**

> **Status:** demo-scale by design. This repo shows *patterns* a
> regulated enterprise would industrialize; scope decisions are stated
> where they apply. This README is a living document.

## The one-sentence architecture

Every request passes **two policy gates** before touching data
(permission rules the developer cannot override, then a risk-tiered
tool gateway), every action lands **attributed** in an append-only
audit trail, and the deliverable itself renders through **entitlement**
— the same analysis shows different screens to different roles.

See the full flow: [docs/security-flow.md](docs/security-flow.md)

## What's demonstrated

| Layer | Mechanism | Where |
|---|---|---|
| Governed development | `CLAUDE.md` standards + managed-settings deny rules (secrets, raw egress, destructive commands) | `.claude/settings.json`, `CLAUDE.md` |
| Governed tool execution | Policy-gated FRED MCP gateway: risk tiers, block-before-handler on critical tier, agent+session attribution | `gateway/fred_gateway.py` |
| Attributed audit | Append-only, scrubbed JSONL — tool, tier, outcome, actor, time; never data values | `audit/` |
| Analysis integrity | Plan-before-act, sanity checks on every claim, provenance and stated limitations in every deliverable | `CLAUDE.md` rules 4–6, `analysis/` |
| ABAC delivery | Role-aware rendering: CEO aggregate vs. analyst detail; restricted series render only with entitlement | `main.py --role <role>` |

## Quickstart

```bash
# Requires Python 3.12+, uv, and Claude Code
git clone <repo-url> && cd fintechco-quant
cp .env.example .env                 # add your FRED_API_KEY (free: fred.stlouisfed.org)
./setup_demo.sh                      # recreates local demo fixtures (see note below)
uv sync
uv run python gateway/fred_gateway.py --selftest

# Register the governed gateway with Claude Code
claude mcp add fred-gateway -- uv run python gateway/fred_gateway.py

# The finale, standalone
uv run python main.py --role analyst
uv run python main.py --role ceo
```

**Note on `setup_demo.sh`:** the deny-rule demonstration requires a
mock `secrets/credentials.env` in the working tree. It is deliberately
NOT committed (a repo teaching secrets hygiene does not ship a secrets
file, even a fake one); the setup script recreates it locally.

## The demo, as performed

The scripted walkthrough — acts, timings, and recovery moves:
[docs/demo-script.md](docs/demo-script.md)

## Why it's built this way

Each design principle is stated with the demo beat that **proves it
live** and the artifact a skeptic can inspect:
[docs/philosophy.md](docs/philosophy.md)

Highlights: *the deny rule wins arguments the prompt would lose* ·
*every claim carries its check* · *permit, log, or block — decided per
action, before the handler runs* · *the same analysis, two screens —
entitlement decides.*

## Production path (deliberately deferred)

Demo-scale honesty, stated: in production, permission policy ships via
IT-managed settings (user-immutable); viewer attributes come from the
IdP with decisions from a policy engine; the audit trail lands in the
enterprise SIEM; and gateway-style controls generalize across every
MCP server behind a portal — the pattern the industry is converging on.

## License

TBD