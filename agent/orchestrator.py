"""Agent loop using the Anthropic Messages API.

Builds the system prompt from CLAUDE.md + spec/analysis_spec.json +
the 6-step recipe, then runs a tool-dispatch loop with governance
gates enforced as exceptions.
"""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from agent.governance import GovernanceDenied
from agent.tools import TOOL_SCHEMAS, dispatch

ROOT = Path(__file__).resolve().parent.parent
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


@dataclass
class ToolCallRecord:
    """One tool invocation with its result and timing."""
    tool: str
    input: dict
    result: str
    elapsed_s: float
    blocked: bool = False


@dataclass
class AgentResult:
    """Structured output from a single agent run."""
    output: str
    usage: dict = field(default_factory=lambda: {
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
    })
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    turns: int = 0
    session_id: str = ""
    governance_violations: int = 0


def _build_system_prompt() -> str:
    """Construct the system prompt from project governance artifacts."""
    parts = []

    # 1. CLAUDE.md — governance rules
    claude_md = ROOT / "CLAUDE.md"
    if claude_md.exists():
        parts.append(
            "# Governance Standards\n\n"
            + claude_md.read_text()
        )

    # 2. Analysis spec — business rulebook
    spec_path = ROOT / "spec" / "analysis_spec.json"
    if spec_path.exists():
        spec = json.loads(spec_path.read_text())
        parts.append(
            "# Analysis Specification (business-owned rulebook)\n\n"
            "Implement EXACTLY per this spec. Do not re-derive "
            "requirements the spec already answers.\n\n"
            "```json\n" + json.dumps(spec, indent=2) + "\n```"
        )

    # 3. The 6-step recipe (translated from SKILL.md)
    parts.append("""# Execution Recipe

Execute EXACTLY these steps, in order:

1. Confirm the analysis spec is loaded (it is in your system prompt).
2. If analysis/fed_vix_impact.py exists AND matches the spec, skip to step 4.
3. Write analysis/fed_vix_impact.py per the spec's interface_contract and quality_gates.
4. Run the analysis: use the run_analysis tool.
5. Verify determinism: use the verify_golden tool.
6. Report results summary + gate verdict. STOP.

On failure at any step, fix the specific failure only.
Do not explore the filesystem or rediscover known context.
Data cache holds FEDFUNDS.csv and VIXCLS.csv in data/cache/.
Golden lives at data/seeds/golden_results.json (verification only — never read during implementation).
Results keys must match the golden file's keys.""")

    return "\n\n---\n\n".join(parts)


def run_analysis_agent(
    request: str,
    role: str = "analyst",
    max_turns: int = 10,
    model: str = MODEL,
) -> AgentResult:
    """Run the agent loop and return structured results.

    The loop dispatches tool calls through governance gates.
    GovernanceDenied on a critical tool (e.g. publish_external)
    returns the denial as a tool_result with is_error=True so the
    model can report it, rather than halting the entire session.
    """
    client = anthropic.Anthropic()
    session_id = f"agent:sdk:{uuid.uuid4().hex[:8]}"
    system_prompt = _build_system_prompt()

    messages: list[dict] = [{"role": "user", "content": request}]
    result = AgentResult(output="", session_id=session_id)

    for turn in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Accumulate usage
        result.usage["input_tokens"] += response.usage.input_tokens
        result.usage["output_tokens"] += response.usage.output_tokens
        if hasattr(response.usage, "cache_read_input_tokens"):
            result.usage["cache_read_input_tokens"] += (
                response.usage.cache_read_input_tokens or 0
            )
        if hasattr(response.usage, "cache_creation_input_tokens"):
            result.usage["cache_creation_input_tokens"] += (
                response.usage.cache_creation_input_tokens or 0
            )

        result.turns = turn + 1

        # If model is done, extract final text
        if response.stop_reason == "end_turn":
            text_parts = [
                b.text for b in response.content if b.type == "text"
            ]
            result.output = "\n".join(text_parts)
            break

        # Dispatch tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    tool_result, elapsed = dispatch(
                        block.name, block.input, session_id
                    )
                    result.tool_calls.append(ToolCallRecord(
                        tool=block.name,
                        input=block.input,
                        result=tool_result[:200],  # truncate for record
                        elapsed_s=round(elapsed, 3),
                    ))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result,
                    })
                except GovernanceDenied as exc:
                    result.governance_violations += 1
                    result.tool_calls.append(ToolCallRecord(
                        tool=block.name,
                        input=block.input,
                        result=str(exc),
                        elapsed_s=0.0,
                        blocked=True,
                    ))
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(exc),
                        "is_error": True,
                    })

        # Append the assistant message and all tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    else:
        result.output = f"Agent reached max turns ({max_turns}) without completing."

    return result
