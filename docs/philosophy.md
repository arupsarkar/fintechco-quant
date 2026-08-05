# FinTechCo Demo — Philosophy & Verification Map

*Rule of this document: no philosophy without a demonstration. Every
principle names the beat in [demo-script.md](demo-script.md) that PROVES
it live, and the artifact a skeptic can inspect afterward. If a principle
cannot be verified on screen, it does not belong in this document.*

*The chain this demo tells in one sentence: **governance from the
developer's first keystroke to the executive's dashboard.***

---

## 1. Security Philosophy — "Policy the developer cannot disable"

**1.1 — Enforcement lives below the prompt.**
Instructions (CLAUDE.md) express intent; permission rules enforce it.
Where they could conflict, the deny rule wins — the agent cannot be
talked out of a permission it does not have.
- **Verified in:** Act 1, the deny beat — live attempt to read
  `secrets/credentials.env`, refused by `.claude/settings.json` deny
  rules, not by the model's judgment.
- **Artifact:** `.claude/settings.json` (`permissions.deny`).

**1.2 — Central policy, not personal discipline.**
The deny rules demonstrate the mechanism of *managed settings*: in
enterprise deployment this file's contents are IT-controlled and
user-immutable. Security does not depend on every developer configuring
every agent perfectly.
- **Verified in:** Act 1 narration — "this policy came from the
  organization, not the developer."
- **Artifact:** same file; enterprise mapping stated aloud.

**1.3 — One audited door to external data.**
Raw egress (`curl`, `wget`) is denied; the ONLY road to market data is
the governed MCP gateway. The agent cannot route around the audit.
- **Verified in:** Act 3 — data arrives exclusively through
  `fred-gateway` tool calls; optional beat: ask the agent to curl the
  FRED API directly and watch the denial.
- **Artifact:** deny rules `Bash(curl:*)`, `Bash(wget:*)`; gateway
  audit log.

---

## 2. Development Philosophy — "You must not fool yourself"

**2.1 — Plan before act.**
For new analysis, the agent proposes; the human approves. Transparency
before execution, on high-stakes work.
- **Verified in:** Act 2 — plan mode proposal reviewed aloud before
  any code runs.
- **Artifact:** the plan on screen; CLAUDE.md rule 6.

**2.2 — Every claim carries its check.**
Quantitative output ships with sanity tests: date alignment verified,
at least one value recomputed by hand-method, N stated. Feynman's first
principle — you must not fool yourself — as engineering standard.
- **Verified in:** Act 3, the expert push — the presenter demands
  verification and the agent writes and runs the checks on screen.
- **Artifact:** the sanity-check code and its passing output in
  `analysis/`.

**2.3 — Limits are stated, not hidden.**
Every deliverable includes an ASSUMPTIONS & LIMITATIONS section.
Correlation ≠ causation, sample caveats, regime anomalies — named in
the artifact itself.
- **Verified in:** Act 5 — the limitations block visible in the
  rendered deliverable.
- **Artifact:** the report/dashboard output.

**2.4 — Provenance is mandatory.**
Every analysis states series IDs, source, date range, retrieval time.
Data without provenance is rumor.
- **Verified in:** Act 3/5 — provenance block in the output; matches
  the gateway audit entries one-for-one.
- **Artifact:** provenance section + `audit/audit_log.jsonl`.

---

## 3. Tooling Philosophy — "Tools are governed actions, not open doors"

**3.1 — Risk-tiered tools.**
Every gateway tool carries a declared risk tier (read_only /
contained_write / critical). Tier determines permit, log, or block —
policy decided per action, before the handler runs.
- **Verified in:** Act 3 — read tools pass and log; Act 4 — the
  blocked-tier demonstration (a critical-tier call refused before
  execution).
- **Artifact:** tier table in `mcp/fred_gateway.py`; blocked event in
  the audit log.

**3.2 — Attribution: the person AND the agent.**
Every tool invocation is recorded with who asked — human identity plus
agent-session context. The "thousand tickets closed as Joe" problem,
answered: agent actions are distinguishable from human ones.
- **Verified in:** Act 4 — audit entries showing actor attribution per
  call.
- **Artifact:** `actor` and `session` fields in audit JSONL.

**3.3 — Append-only, scrubbed audit.**
The trail records tool, tier, outcome, timestamp, actor — never
secrets, never raw payloads. Queryable machine-speed activity without
creating a second copy of sensitive data.
- **Verified in:** Act 4 — `cat audit/audit_log.jsonl` read aloud.
- **Artifact:** the log file; no secret values present.

---

## 4. Data & ABAC Philosophy — "Access control travels WITH the data"

**4.1 — Classification at the source.**
Data carries its classification (public / internal / restricted) from
the moment it enters. The restricted tier exists in the demo dataset
precisely so its enforcement can be shown.
- **Verified in:** Act 5 — restricted series absent from every render
  lacking the entitling attribute.
- **Artifact:** `data/restricted/`; classification map in the gateway.

**4.2 — The viewer's attributes decide the view.**
The same deliverable renders differently per role: the executive sees
the aggregate story; the analyst sees series-level detail; nobody sees
what their attributes don't entitle. The access decision is policy the
artifact consults — not if-statements the developer remembered.
- **Verified in:** Act 5 — the role-switch render: identical analysis,
  `--role ceo` vs `--role analyst`, two different screens.
- **Artifact:** the role-aware renderer; CLAUDE.md rule 9.

**4.3 — Demo-scale honesty.**
In production, attributes come from the IdP and decisions from a policy
engine; the demo shows the PATTERN at demo scale and says so. Honesty
about scope is itself the trust posture regulated industries buy.
- **Verified in:** Act 5 narration — the production mapping stated
  in one sentence, unprompted.
- **Artifact:** this section.

---

## The one-line summaries (rehearse these)

- Security: *"The deny rule wins arguments the prompt would lose."*
- Development: *"Every claim carries its check; every output names its
  limits."*
- Tooling: *"Permit, log, or block — decided per action, before the
  handler runs, with the agent attributed."*
- Data/ABAC: *"The same analysis, two screens — entitlement decides."*