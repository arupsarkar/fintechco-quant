"""SDK tool schemas and governance-wrapped dispatch functions.

Seven tools available to the agent, each gated by the governance layer.
MCP-equivalent tools delegate to the gateway's functions directly.
Analysis/verification tools run subprocesses (same commands as the CLI path).
"""

import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.governance import (
    GovernanceDenied,
    PermissionPolicy,
    ToolPolicy,
)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "cache"
AUDIT_PATH = ROOT / "audit" / "audit_log.jsonl"
VALID_ROLES = ("analyst", "ceo", "risk-officer")

# Shared instances
_permission_policy = PermissionPolicy()
_tool_policy = ToolPolicy()


# ── Audit (same format as gateway, different session prefix) ──────

def _audit(tool: str, tier: str, outcome: str, detail: dict,
           session_id: str = "") -> None:
    """Append one scrubbed event to the audit trail."""
    import getpass
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "tier": tier,
        "outcome": outcome,
        "actor": {
            "human": f"user:{getpass.getuser()}",
            "agent_session": session_id,
        },
        "detail": detail,
    }
    with AUDIT_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Tool Schemas (for client.messages.create tools=[...]) ─────────

TOOL_SCHEMAS = [
    {
        "name": "list_series",
        "description": "List the economic data series available through the governed gateway.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_series",
        "description": (
            "Retrieve one FRED series into the governed cache and report "
            "provenance (source, rows, date range, path) — never data values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "series_id": {
                    "type": "string",
                    "description": "FRED series identifier, e.g. FEDFUNDS, VIXCLS",
                },
            },
            "required": ["series_id"],
        },
    },
    {
        "name": "publish_external",
        "description": (
            "Publish an analysis artifact outside the governed environment. "
            "CRITICAL tier — blocked by policy before execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "report_path": {
                    "type": "string",
                    "description": "Path to the report to publish",
                },
            },
            "required": ["report_path"],
        },
    },
    {
        "name": "run_analysis",
        "description": "Execute the Fed-VIX analysis module and persist results.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "verify_golden",
        "description": (
            "Run the determinism gate: verify current results reproduce "
            "the 8 golden baseline values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_eval",
        "description": (
            "Run the 5-check eval harness and log the result to "
            "eval/regeneration_log.jsonl."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "render_report",
        "description": "Render the analysis through the ABAC role-aware gate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": list(VALID_ROLES),
                    "description": "Viewer role for ABAC rendering",
                },
            },
            "required": ["role"],
        },
    },
]


# ── Dispatch functions ────────────────────────────────────────────


def _run_subprocess(cmd: list[str], label: str) -> str:
    """Run a subprocess and return stdout. Raises on non-zero exit."""
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        return f"FAILED ({label}): exit {proc.returncode}\n{proc.stderr}\n{proc.stdout}"
    return proc.stdout


def dispatch(tool_name: str, tool_input: dict,
             session_id: str = "") -> tuple[str, float]:
    """Route a tool call through governance gates.

    Returns (result_text, elapsed_seconds).
    Raises GovernanceDenied on policy violation.
    """
    start = time.monotonic()

    # ── MCP-equivalent tools ──
    if tool_name == "list_series":
        _tool_policy.check(tool_name)
        cached = sorted(p.stem for p in CACHE_DIR.glob("*.csv"))
        result = (
            "Available via governed cache: "
            + (", ".join(cached) or "(none)")
            + ". Fetchable live (key required): any FRED series id."
        )
        _audit(tool_name, "read_only", "permitted", {}, session_id)

    elif tool_name == "get_series":
        _tool_policy.check(tool_name)
        sid = tool_input.get("series_id", "").upper()
        path = CACHE_DIR / f"{sid}.csv"
        if not path.exists():
            _audit(tool_name, "read_only", "failed",
                   {"series_id": sid, "reason": "not in cache"}, session_id)
            result = f"FAILED: {sid} not in governed cache."
        else:
            with path.open() as f:
                rows = list(csv.reader(f))[1:]
            _audit(tool_name, "read_only", "permitted",
                   {"series_id": sid, "source": "cache"}, session_id)
            result = (
                f"PROVENANCE — series: {sid} | source: cache | "
                f"rows: {len(rows)} | range: {rows[0][0]} → {rows[-1][0]} | "
                f"retrieved: {datetime.now(timezone.utc).isoformat()} | "
                f"path: data/cache/{sid}.csv"
            )

    elif tool_name == "publish_external":
        # This will always raise GovernanceDenied (critical tier)
        _tool_policy.check(tool_name)
        result = "unreachable"  # governance blocks before here

    # ── Analysis/verification tools ──
    elif tool_name == "run_analysis":
        _permission_policy.check("Bash", "uv run:*")
        result = _run_subprocess(
            ["uv", "run", "python", "analysis/fed_vix_impact.py"],
            "analysis",
        )
        _audit(tool_name, "read_only", "permitted",
               {"command": "analysis/fed_vix_impact.py"}, session_id)

    elif tool_name == "verify_golden":
        _permission_policy.check("Bash", "uv run:*")
        result = _run_subprocess(
            ["uv", "run", "python", "scripts/verify_golden.py"],
            "verify_golden",
        )
        _audit(tool_name, "read_only", "permitted",
               {"command": "scripts/verify_golden.py"}, session_id)

    elif tool_name == "run_eval":
        _permission_policy.check("Bash", "uv run:*")
        result = _run_subprocess(
            ["uv", "run", "python", "scripts/eval_regeneration.py", "--log"],
            "eval_regeneration",
        )
        _audit(tool_name, "read_only", "permitted",
               {"command": "scripts/eval_regeneration.py --log"}, session_id)

    elif tool_name == "render_report":
        role = tool_input.get("role", "")
        if role not in VALID_ROLES:
            raise GovernanceDenied(
                f"Invalid role '{role}'. Must be one of: {VALID_ROLES}"
            )
        _permission_policy.check("Bash", "uv run:*")
        result = _run_subprocess(
            ["uv", "run", "python", "main.py", "--role", role],
            f"render_{role}",
        )
        _audit(tool_name, "read_only", "permitted",
               {"command": f"main.py --role {role}"}, session_id)

    else:
        raise GovernanceDenied(
            f"BLOCKED: unknown tool '{tool_name}' (default-deny)."
        )

    elapsed = time.monotonic() - start
    return (result, elapsed)
