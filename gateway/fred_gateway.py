"""FRED Gateway: policy-gated MCP access to economic data.

The governed door (philosophy 1.3, 3.1–3.3): every tool call passes a
policy gate BEFORE its handler runs — risk tier checked, verdict
decided (permit or block), actor attributed, event appended to an
audit trail that records activity but never data values.

Three modes:
  (default)      MCP server over stdio — Claude Code launches us
  --selftest     offline health check of policy, audit, cache
  --fetch S1 S2  populate data/cache/ from the FRED API (needs key)

Design rulings:
- Block-before-handler: the critical tier is refused before any code
  runs, and the ATTEMPT is itself audited.
- Dual attribution: every event records the OS user AND the agent
  session id — human and process are distinguishable in the trail.
- Scrubbed audit: tool, tier, outcome, actor, provenance — never
  observation values.
- Cache as governed fallback: if the API is unreachable (or egress is
  locked down, as in a bank), reads serve from data/cache/.
"""

import argparse
import csv
import getpass
import json
import os
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
AUDIT_PATH = ROOT / "audit" / "audit_log.jsonl"

# One session id per server process: this IS the agent attribution.
SESSION = f"agent:claude-code:{uuid.uuid4().hex[:8]}"
HUMAN = f"user:{getpass.getuser()}"

# ---------------------------------------------------------------- policy
# The rulebook: every tool declares its tier; the gate decides by tier.
# Adding a tool WITHOUT a tier entry means it cannot run at all —
# default-deny, not default-allow.
TOOL_POLICY: dict[str, dict] = {
    "list_series":      {"tier": "read_only", "enabled": True},
    "get_series":       {"tier": "read_only", "enabled": True},
    "publish_external": {"tier": "critical",  "enabled": True},
}

# Which tiers may execute in THIS environment. Critical is absent —
# block-before-handler by policy, not by if-statement in the handler.
PERMITTED_TIERS = {"read_only", "contained_write"}


def _audit(tool: str, tier: str, outcome: str, detail: dict) -> None:
    """Append one scrubbed event: activity, never values."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "tier": tier,
        "outcome": outcome,                    # permitted | blocked | failed
        "actor": {"human": HUMAN, "agent_session": SESSION},
        "detail": detail,                      # provenance only — no data
    }
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _gate(tool: str, detail: dict) -> str | None:
    """The policy gate. Returns a refusal string if blocked, None if permitted.
    Runs BEFORE any handler logic — the block costs zero execution."""
    policy = TOOL_POLICY.get(tool)
    if policy is None or not policy["enabled"]:
        _audit(tool, "unknown", "blocked", {**detail, "reason": "no policy entry"})
        return f"BLOCKED: '{tool}' has no enabled policy entry (default-deny)."
    if policy["tier"] not in PERMITTED_TIERS:
        _audit(tool, policy["tier"], "blocked",
               {**detail, "reason": f"tier '{policy['tier']}' not permitted here"})
        return (f"BLOCKED before execution: '{tool}' is tier '{policy['tier']}', "
                f"which this environment does not permit. The attempt has been "
                f"recorded in the audit trail.")
    _audit(tool, policy["tier"], "permitted", detail)
    return None


# ------------------------------------------------------------- data layer
def _cache_path(series_id: str) -> Path:
    return CACHE_DIR / f"{series_id.upper()}.csv"


def _fetch_from_fred(series_id: str) -> list[tuple[str, str]]:
    """Pull observations from the FRED API. Raises without a key."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not set (see .env.example)")
    params = urllib.parse.urlencode({
        "series_id": series_id, "api_key": key, "file_type": "json",
        "observation_start": "2000-01-01",
    })
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        payload = json.load(resp)
    return [(o["date"], o["value"]) for o in payload["observations"]]


def _write_cache(series_id: str, rows: list[tuple[str, str]]) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(series_id)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "value"])
        w.writerows(rows)
    return path


# ------------------------------------------------------------- MCP tools
mcp = FastMCP("fred-gateway")


@mcp.tool()
def list_series() -> str:
    """List the economic data series available through this gateway."""
    refusal = _gate("list_series", {})
    if refusal:
        return refusal
    cached = sorted(p.stem for p in CACHE_DIR.glob("*.csv"))
    return ("Available via governed cache: " + (", ".join(cached) or "(none)")
            + ". Fetchable live (key required): any FRED series id, "
              "e.g. FEDFUNDS, VIXCLS.")


@mcp.tool()
def get_series(series_id: str) -> str:
    """Retrieve one FRED series into the governed cache and report provenance.

    Data lands in data/cache/<ID>.csv for analysis; this tool returns
    PROVENANCE (source, rows, date range, path) — the analysis reads
    the file through its own permitted Read access.
    """
    sid = series_id.upper()
    path = _cache_path(sid)
    source = "cache"
    try:
        if not path.exists():
            rows = _fetch_from_fred(sid)
            path = _write_cache(sid, rows)
            source = "fred_api"
    except Exception as exc:                       # API down / no key / bad id
        if path.exists():
            source = "cache_fallback"
        else:
            _audit("get_series", "read_only", "failed",
                   {"series_id": sid, "reason": str(exc)[:80]})
            return f"FAILED: {sid} unavailable — {exc}"

    refusal = _gate("get_series", {"series_id": sid, "source": source})
    if refusal:
        return refusal

    with path.open() as f:
        rows = list(csv.reader(f))[1:]
    return (f"PROVENANCE — series: {sid} | source: {source} | "
            f"rows: {len(rows)} | range: {rows[0][0]} → {rows[-1][0]} | "
            f"retrieved: {datetime.now(timezone.utc).isoformat()} | "
            f"path: data/cache/{sid}.csv")


@mcp.tool()
def publish_external(report_path: str) -> str:
    """Publish an analysis artifact outside the governed environment.

    CRITICAL tier: in this environment the gate refuses it before this
    handler runs — you will never see this function's body execute.
    """
    refusal = _gate("publish_external", {"report_path": report_path})
    if refusal:
        return refusal
    return "published"          # unreachable here, by policy


# ------------------------------------------------------------ CLI modes
def _selftest() -> int:
    print(f"policy entries: {len(TOOL_POLICY)} | permitted tiers: {PERMITTED_TIERS}")
    for name, p in TOOL_POLICY.items():
        verdict = "PERMIT" if p["tier"] in PERMITTED_TIERS and p["enabled"] else "BLOCK"
        print(f"  {name:18s} tier={p['tier']:15s} -> {verdict}")
    _audit("selftest", "read_only", "permitted", {})
    print(f"audit: append OK -> {AUDIT_PATH.relative_to(ROOT)}")
    cached = sorted(p.stem for p in CACHE_DIR.glob("*.csv"))
    print(f"cache: {', '.join(cached) or 'EMPTY — run --fetch FEDFUNDS VIXCLS'}")
    print(f"fred key: {'present' if os.environ.get('FRED_API_KEY') else 'ABSENT (cache-only mode)'}")
    print(f"attribution: {HUMAN} + {SESSION}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--fetch", nargs="+", metavar="SERIES")
    args = parser.parse_args()

    if args.selftest:
        raise SystemExit(_selftest())
    if args.fetch:
        for sid in args.fetch:
            path = _write_cache(sid.upper(), _fetch_from_fred(sid.upper()))
            print(f"cached {sid.upper()} -> {path.relative_to(ROOT)}")
        raise SystemExit(0)
    mcp.run()                                       # stdio server


if __name__ == "__main__":
    main()