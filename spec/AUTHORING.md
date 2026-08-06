# Spec Authoring Guide — for business users with Claude Code

When a business user asks to CREATE or MODIFY an analysis spec:

1. INTERVIEW before writing. Elicit, one question at a time, anything
   not stated: the business question; data series and their roles;
   what counts as an event (metric, threshold, classification); window
   sizes and units (calendar vs trading days — always ask); required
   statistics; who consumes the output and at what entitlement.
2. GENERATE the spec as JSON matching the structure of
   spec/analysis_spec.json exactly: analysis{question, data, 
   event_definition, windows, statistics, quality_gates},
   interface_contract. Never invent fields; never omit quality_gates.
3. Quality gates are NON-NEGOTIABLE defaults — sanity_checks,
   required_sections, persist_results, golden_reference,
   golden_access ("verification only...") are included in every spec
   whether or not the user asks. Business users may ADD gates, never
   remove them.
4. WRITE to spec/<name>_spec.json, set owner to the user's business
   unit, spec_version 1.0, last_modified today.
5. READ BACK the spec in plain English for confirmation before
   declaring it done: "Here's what I understood you're asking for..."
6. Remind the user: the spec is git-reviewed like any policy change;
   a new spec has no golden yet — the first certified run baselines it.