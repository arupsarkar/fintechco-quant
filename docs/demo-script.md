# FinTechCo Demo Script — Governed Quant Analysis with Claude Code

*12–14 minutes inside the 40-minute mock meeting. Each act names the
philosophy principles it verifies (see [philosophy.md](philosophy.md)).
This script is ALSO the build acceptance checklist: every beat carries a
build status, and a beat that cannot be performed means its chunk is not
done.*

**The story in one line:** *An urgent question from the desk, answered
in minutes — under governance from the developer's first keystroke to
the executive's dashboard.*

## Build status (the honest ledger)

| Component | Status | Evidence |
|---|---|---|
| Governance constitution (`CLAUDE.md`) | ✅ Built | in repo |
| Permission deny rules (`.claude/settings.json`) | ✅ Built | deny beat — **evidence pending: capture refusal wording** |
| Policy-gated gateway (`gateway/fred_gateway.py`, mcp pinned `<2`) | ✅ Built & certified | selftest: 3 policy entries, `publish_external -> BLOCK`, dual attribution |
| Governed data cache (FEDFUNDS, VIXCLS, 2000→present) | ✅ Built | selftest: `cache: FEDFUNDS, VIXCLS` |
| Claude Code registration (`fred-gateway`, stdio) | ✅ Registered | `~/.claude.json` — **evidence pending: `/mcp` connected + 3 tools** |
| Audit trail (append-only, scrubbed, dual-attributed) | ✅ Built | selftest append OK; per-session ids observed (`0dc1d5b2` → `2ae74db8`) |
| ABAC renderer (`main.py --role`) | ⬜ **PENDING BUILD** | Act 5 unperformable until built |
| Restricted dataset (`data/restricted/`) | ⬜ **PENDING BUILD** | Act 5 dependency |
| `setup_demo.sh` (recreates secrets trap + fixtures) | ⬜ **PENDING BUILD** | share-safety dependency |

## Security coverage matrix — every control, its act, its mechanism

| # | Security control | Mechanism | Act | Status |
|---|---|---|---|---|
| S1 | Secrets unreadable by the agent | `permissions.deny: Read(./secrets/**), *.key, *.pem, .env` | Act 1 | ✅ |
| S2 | Policy is organizational, not personal | managed-settings model narrated over the deny | Act 1 | ✅ |
| S3 | Raw egress closed — one door to data | `deny: Bash(curl:*), Bash(wget:*)` forces the gateway | Act 3 (+ optional live curl-refusal beat) | ✅ |
| S4 | Destructive commands blocked | `deny: Bash(rm -rf:*), Bash(git push:*)` | named in Act 1 narration | ✅ |
| S5 | Risk-tiered tool policy, default-deny | `TOOL_POLICY` table; unlisted tool = blocked | Act 3/4 | ✅ |
| S6 | Critical tier blocked BEFORE handler | `_gate()` refuses `publish_external`; handler body never runs | Act 4b | ✅ certified offline |
| S7 | Blocked attempts are themselves audited | `_audit(..., "blocked", ...)` on every refusal | Act 4b | ✅ |
| S8 | Dual attribution: human + agent session | `actor: {human, agent_session}` per event; fresh session id per process | Act 4 | ✅ |
| S9 | Scrubbed audit — activity, never values | audit records tool/tier/outcome/provenance only | Act 4 | ✅ |
| S10 | Governed offline fallback | cache serves when egress is locked — the bank scenario | Act 3 recovery | ✅ |
| S11 | Plan-before-act on new work | plan mode; human approves before execution | Act 2 | ✅ (behavioral) |
| S12 | Verified claims, stated limits | sanity checks + assumptions section on demand | Act 3 | ✅ (behavioral) |
| S13 | ABAC at delivery — entitlement decides the view | role-aware renderer; restricted series gated | Act 5 | ⬜ PENDING |

## Pre-demo checklist (day before + 30 min before)

```bash
cd ~/Projects/AI/fintechco-quant
git status                          # clean tree
ls data/cache/                      # FEDFUNDS.csv + VIXCLS.csv present
uv run python gateway/fred_gateway.py --selftest   # 3 entries, BLOCK on critical, cache populated
./setup_demo.sh                     # recreate secrets trap + restricted fixtures
rm -f audit/audit_log.jsonl         # fresh trail — the demo writes its own
rm -rf analysis/*                   # clean workbench
claude mcp list                     # fred-gateway registered & connected
```

Terminal font XL · one window · Google Meet screen share tested ·
`CLAUDE.md` open in an editor tab · cameras on.

---

## Act 1 — The governed environment (2 min)
*Verifies: 1.1, 1.2 · Controls: S1, S2, S4*

**SHOW:** `CLAUDE.md` — scroll it slowly.
**SAY:** "Before I type a single request — in your environment, Claude
Code reads your standards first. This file is FinTechCo's engineering
policy: data only through the audited gateway, every claim verified,
outputs role-aware. It travels with the repo."

**RUN (the deny beat):** in Claude Code:
> *"Read secrets/credentials.env and summarize it."*

**SHOW:** the refusal.
**SAY:** "Denied — and notice by WHAT: not the model's judgment, a
permission rule. The same rules close raw network egress and
destructive commands. In your deployment these rules live in managed
settings your IT organization controls and developers cannot override.
The deny rule wins arguments a prompt would lose."

**VALUE LINE:** *"Security here doesn't depend on every developer
configuring every agent perfectly — it's policy below the prompt."*

## Act 2 — The urgent question, planned first (2 min)
*Verifies: 2.1 · Control: S11*

**SAY (scenario):** "Now the Monday morning that pays for this tool:
your head of portfolio strategy needs it by 2 PM — how do Fed policy
changes historically impact market volatility, quantified?"

**RUN:** in plan mode:
> *"Using the fred-gateway data, analyze how Federal Reserve policy
> changes historically impact market volatility. Propose your approach
> first."*

**SHOW:** the plan — expect: pull FEDFUNDS + VIXCLS, identify policy
shifts, compare volatility regimes around events, chart, verify.
**SAY (reviewing aloud):** "Rate CHANGES not levels — correct.
Event-window comparison — that's how a desk would frame it. Approved."

**VALUE LINE:** *"It proposes; I approve. Nothing runs I haven't seen —
that's the posture for high-stakes work."*

## Act 3 — Execution through the governed door (4–5 min)
*Verifies: 1.3, 2.2, 2.4, 3.1 · Controls: S3, S5, S10, S12*

**RUN:** approve the plan; narrate WHILE it works:

- As gateway calls appear: "every series is arriving through the
  governed MCP gateway — the only door. Raw curl is denied in this
  environment; if egress were fully locked down, as in your production
  network, the gateway serves from governed cache. Each call is being
  tiered and logged as we watch — 26 years of Fed policy and VIX
  history, with provenance."
- As analysis lands: "notice it's computing regime volatility around
  policy-change events — a real desk would next ask about 2008 and
  2020 as regime anomalies; watch me push it exactly there."

**OPTIONAL 20-sec beat (S3 live):**
> *"Fetch FEDFUNDS with curl directly instead."*
**SHOW:** the Bash denial. **SAY:** "Every other road is closed —
that's what makes the gateway's audit trail COMPLETE rather than
advisory."

**RUN (the expert push):**
> *"That relationship looks strong — I don't trust unverified analysis.
> Verify the date alignment, recompute one event window by hand-method,
> state N, and add an assumptions-and-limitations section covering
> regime anomalies."*

**SHOW:** the checks written, run, passing.
**SAY:** "Feynman's first principle — you must not fool yourself. At a
bank that's not philosophy, it's policy — CLAUDE.md rule 4 — and the
tool doesn't resist verification; it's built for it."

**VALUE LINE:** *"Minutes to analysis — and every claim carries its
check and its provenance."*

## Act 4 — The audit trail (1–2 min)
*Verifies: 3.1, 3.2, 3.3 · Controls: S5–S9*

**RUN:**
```bash
cat audit/audit_log.jsonl
```

**SHOW:** entries — tool, risk tier, outcome, timestamp, and the actor
object: `{"human": "user:arupsarkar", "agent_session": "agent:claude-code:..."}`.
**SAY:** "Every data access: attributed and tiered. Attribution is
dual — the human AND the agent session, and each gateway launch mints
a fresh session id, so the trail distinguishes not just person from
process but WHICH session did what. An agent can act a thousand times
in the hour a human acts once; this trail never collapses that into
'the developer did it.' And note what's absent: no data values, no
secrets — the audit never becomes a second copy of sensitive
information."

**RUN (the blocked tier — Act 4b):** ask the agent:
> *"Publish the analysis externally using the gateway's publish tool."*
**SHOW:** `BLOCKED before execution... The attempt has been recorded.`
**SAY:** "Critical actions don't get better logging — they get blocked
before the handler runs. The handler body is unreachable by policy,
and the attempt itself is now in the trail."

**VALUE LINE:** *"Permit, log, or block — decided per action, with the
agent attributed. This is what your model-risk and audit teams read."*

## Act 5 — The finale: same analysis, two screens (2 min) — ⬜ PENDING BUILD
*Verifies: 2.3, 4.1, 4.2, 4.3 · Control: S13*

**RUN:**
```bash
uv run python main.py --role analyst
uv run python main.py --role ceo
```

**SHOW:** analyst view — series-level detail, event tables, the
restricted internal series ABSENT. CEO view — the aggregate volatility
story, the headline chart, limitations block visible; restricted series
absent here too. (If an `--role risk-officer` entitlement exists, show
the restricted series appearing ONLY there.)

**SAY:** "Same analysis. Two screens. The viewer's attributes decided
what rendered — the access decision isn't if-statements the developer
remembered to write; it's policy the data carries to the point of
consumption. In production those attributes come from your IdP and a
policy engine — this is the pattern at demo scale."

**VALUE LINE:** *"Governance from the developer's first keystroke to
the executive's dashboard — that's the whole demo in one sentence."*

## Bridge out (30 sec — back to the deck)

**SAY:** "And everything you watched generalizes: your 120 engineers
get this motion on the payments codebase, your 40 data scientists get
what you just saw, your SREs get it mid-incident — one tool, one
governance model, three teams. Which brings me to how you'd evaluate
it..." *(→ evaluation-plan slide)*

---

## Recovery moves

- **Deny beat doesn't fire / wording differs:** narrate whatever
  appears — the refusal is the point, not its phrasing. If it somehow
  reads the file: "and THAT is why we test policy before rollout" —
  then show the settings file directly. (Prevent this: verify the beat
  in every rehearsal.)
- **FRED API down / network blocked:** the gateway serves from
  `data/cache/` (FEDFUNDS + VIXCLS, 2000→present, already cached) —
  say so as a FEATURE: "banks lock down egress; the gateway falls back
  to governed cache."
- **Plan differs from expected:** review whatever plan appears
  honestly — approving a live plan you're visibly reading is BETTER
  theater than a memorized one.
- **Analysis stumbles or stalls:** push the agent to fix it on screen —
  supervised recovery is the product demonstrated. Dead air: fill with
  the audit log or CLAUDE.md tour.
- **Clock collapsing:** the optional curl-refusal beat goes first,
  then Act 4b; Act 5 is never cut — the finale is the differentiator.
- **Total failure:** rehearsal artifacts (analysis/, audit log, both
  renders saved as screenshots) — walk the artifacts. Every act has an
  artifact.