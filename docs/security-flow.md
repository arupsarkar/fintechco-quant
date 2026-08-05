# FinTechCo Quant — Governed Request Flow

*One request, end to end: developer keystroke → governed environment →
policy-gated data access → attributed audit → role-aware delivery.
Zones map to the demo acts (noted at the bottom).*

```mermaid
flowchart TD
    classDef human fill:#ffe8d6,stroke:#b45309,color:#7c2d12
    classDef agent fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a
    classDef policy fill:#fef3c7,stroke:#d97706,color:#92400e
    classDef allow fill:#dcfce7,stroke:#15803d,color:#14532d
    classDef block fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d
    classDef data fill:#f1f5f9,stroke:#475569,color:#334155
    classDef audit fill:#ede9fe,stroke:#6d28d9,color:#4c1d95

    DEV(["Developer request<br/><i>'Analyze Fed policy impact on volatility'</i>"]):::human
    CC["Claude Code session<br/>reads CLAUDE.md — FinTechCo standards"]:::agent

    DEV --> CC

    subgraph ENV["&nbsp;GOVERNED ENVIRONMENT — policy below the prompt&nbsp;"]
        PERM{"Permission rules<br/>managed settings — IT-owned"}:::policy
        DENY["⛔ Refused<br/>secrets/*, curl, rm -rf<br/><i>the deny rule wins</i>"]:::block
        PLAN["Plan mode<br/>propose → human approves"]:::allow
    end

    CC --> PERM
    PERM -- "denied action" --> DENY
    PERM -- "permitted" --> PLAN

    subgraph GATE["&nbsp;FRED GATEWAY — policy gate (mini-WriteGuard)&nbsp;"]
        LOAD["Load tool policy + request context<br/><i>risk tier · enabled state · actor · session</i>"]:::policy
        TIER{"Permit this<br/>tool call?"}:::policy
        ATTR["✅ ALLOW<br/>attach agent + session attribution"]:::allow
        BLK["🚫 BLOCK<br/>critical tier — refused<br/>before handler runs"]:::block
        EXEC["Execute tool handler"]:::agent
    end

    PLAN --> LOAD --> TIER
    TIER -- allow --> ATTR --> EXEC
    TIER -- block --> BLK

    FRED["FRED API"]:::data
    CACHE[("data/cache/<br/>governed offline fallback")]:::data
    EXEC --> FRED
    EXEC -. "egress locked?" .-> CACHE

    OUT["Classify outcome<br/>success · failed · blocked"]:::allow
    EXEC --> OUT
    BLK --> OUT

    subgraph AUD["&nbsp;AUDIT SERVICE — async, scrubbed&nbsp;"]
        SCRUB["Redact values & secrets<br/>keep: tool · tier · outcome · actor · time"]:::audit
        LOG[("audit/audit_log.jsonl<br/>append-only")]:::audit
    end

    OUT -. "async event" .-> SCRUB --> LOG

    ART["Analysis artifacts<br/>provenance + sanity checks +<br/>assumptions & limitations"]:::agent
    OUT --> ART

    subgraph ABAC["&nbsp;ROLE-AWARE DELIVERY — access travels with the data&nbsp;"]
        ROLE{"Viewer<br/>attributes?"}:::policy
        CEO["CEO view<br/>aggregate story · headline chart"]:::allow
        ANA["Analyst view<br/>series-level detail · event tables"]:::allow
        RES["🚫 Restricted series<br/>renders ONLY with entitlement"]:::block
    end

    ART --> ROLE
    ROLE -- "role: ceo" --> CEO
    ROLE -- "role: analyst" --> ANA
    ROLE -- "no entitlement" --> RES
```

**Zone → demo act → philosophy:**

| Zone | Demo act | Philosophy verified |
|---|---|---|
| Governed Environment | Act 1 (deny beat) + Act 2 (plan) | 1.1, 1.2, 2.1 |
| FRED Gateway policy gate | Act 3 (governed door) + Act 4b (blocked tier) | 1.3, 3.1, 3.2 |
| Audit Service | Act 4 (`cat` the trail) | 3.2, 3.3 |
| Role-Aware Delivery | Act 5 (two screens finale) | 4.1, 4.2, 4.3 |

*The read of the diagram, spoken in one breath: "every request passes
two policy gates before touching data, every action lands attributed in
an append-only trail, and the deliverable itself renders through
entitlement — governance from keystroke to dashboard."*