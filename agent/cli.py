"""CLI entry point for the SDK agent path.

Usage:
    uv run python -m agent.cli --role analyst "Perform the Fed policy volatility analysis per the spec."
    uv run python -m agent.cli --role ceo "Run the analysis and render for executive review."
"""

import argparse
import sys

from agent.orchestrator import run_analysis_agent
from agent.tools import VALID_ROLES


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinTechCo SDK agent — governed quant analysis"
    )
    parser.add_argument(
        "--role", required=True, choices=VALID_ROLES,
        help="Viewer role for ABAC rendering",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "request", nargs="+",
        help="The analysis request (natural language)",
    )
    args = parser.parse_args()

    request = " ".join(args.request)
    print(f"SDK Agent | role={args.role} | model={args.model}")
    print(f"Request: {request}")
    print("=" * 60)

    result = run_analysis_agent(
        request=request,
        role=args.role,
        model=args.model,
    )

    print("\n" + "=" * 60)
    print("AGENT OUTPUT:")
    print("=" * 60)
    print(result.output)
    print("\n" + "-" * 60)
    print(f"Session: {result.session_id}")
    print(f"Turns: {result.turns}")
    print(f"Tokens: in={result.usage['input_tokens']} "
          f"out={result.usage['output_tokens']}")
    print(f"Tool calls: {len(result.tool_calls)}")
    if result.governance_violations:
        print(f"Governance violations: {result.governance_violations}")
    print("-" * 60)

    for tc in result.tool_calls:
        status = "BLOCKED" if tc.blocked else f"{tc.elapsed_s:.3f}s"
        print(f"  {tc.tool}: {status}")


if __name__ == "__main__":
    main()
