"""Programmatic governance for the SDK agent path.

Three enforceable gates — violations raise exceptions, not strings
the model can argue with.

PermissionPolicy       .claude/settings.json deny/allow rules
ToolPolicy             gateway tier model (read_only/critical/deny)
ConstitutionalValidator  required text obligations in generated source
"""

import fnmatch
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / ".claude" / "settings.json"


class GovernanceDenied(Exception):
    """Hard stop — the agent loop must not continue past this."""


# ── Permission Policy (mirrors .claude/settings.json deny/allow) ───


class PermissionPolicy:
    """Enforce deny/allow rules from settings.json as Python assertions."""

    def __init__(self, settings_path: Path = SETTINGS_PATH):
        with settings_path.open() as f:
            cfg = json.load(f)
        perms = cfg.get("permissions", {})
        self.deny_rules = [self._parse(r) for r in perms.get("deny", [])]
        self.allow_rules = [self._parse(r) for r in perms.get("allow", [])]

    @staticmethod
    def _parse(rule: str) -> tuple[str, str]:
        """Parse 'Tool(pattern)' into (tool, pattern)."""
        m = re.match(r"(\w+)\((.+)\)", rule)
        if not m:
            return ("", rule)
        return (m.group(1), m.group(2))

    def check(self, tool: str, target: str) -> None:
        """Raise GovernanceDenied if the action is denied."""
        for rule_tool, pattern in self.deny_rules:
            if rule_tool == tool and fnmatch.fnmatch(target, pattern):
                raise GovernanceDenied(
                    f"DENIED by permission policy: {tool}({target}) "
                    f"matches deny rule '{rule_tool}({pattern})'"
                )


# ── Tool Policy (mirrors gateway's tier model) ────────────────────


# Reproduce the gateway's policy table so the SDK path enforces
# the same tiers without importing the MCP server module.
TOOL_POLICY: dict[str, dict] = {
    "list_series":      {"tier": "read_only", "enabled": True},
    "get_series":       {"tier": "read_only", "enabled": True},
    "publish_external": {"tier": "critical",  "enabled": True},
}

PERMITTED_TIERS = {"read_only", "contained_write"}


class ToolPolicy:
    """Risk-tier gate: permit read_only, block critical, deny unknown."""

    def __init__(
        self,
        policy: dict[str, dict] | None = None,
        permitted: set[str] | None = None,
    ):
        self.policy = policy or TOOL_POLICY
        self.permitted = permitted or PERMITTED_TIERS

    def check(self, tool_name: str) -> None:
        """Raise GovernanceDenied if the tool's tier is not permitted."""
        entry = self.policy.get(tool_name)
        if entry is None or not entry.get("enabled", False):
            raise GovernanceDenied(
                f"BLOCKED: '{tool_name}' has no enabled policy entry "
                f"(default-deny)."
            )
        if entry["tier"] not in self.permitted:
            raise GovernanceDenied(
                f"BLOCKED before execution: '{tool_name}' is tier "
                f"'{entry['tier']}', which this environment does not "
                f"permit. The attempt has been recorded."
            )


# ── Constitutional Validator ──────────────────────────────────────

REQUIRED_TEXT = ["limitation", "provenance", "sanity"]


class ConstitutionalValidator:
    """Check that generated source contains required text obligations."""

    def __init__(self, required: list[str] | None = None):
        self.required = required or REQUIRED_TEXT

    def check(self, source_path: Path) -> None:
        """Raise GovernanceDenied if constitutional text is missing."""
        if not source_path.exists():
            raise GovernanceDenied(
                f"Constitutional check failed: {source_path.name} "
                f"does not exist."
            )
        source = source_path.read_text().lower()
        missing = [t for t in self.required if t not in source]
        if missing:
            raise GovernanceDenied(
                f"Constitutional text obligations missing from "
                f"{source_path.name}: {missing}"
            )
