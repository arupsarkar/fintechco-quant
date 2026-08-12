"""SDK eval harness: K regenerations via the agent loop, full observability.

Replaces scripts/measure_generation.sh with a Python framework that
captures SDK-only metrics: tool call sequences, governance violations,
per-dispatch latency, and structured cost computation.

Usage:
    uv run python -m agent.eval_harness --k 3 --arm metadata
    uv run python -m agent.eval_harness --k 3 --arm prose
"""

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from agent.orchestrator import AgentResult, run_analysis_agent

ROOT = Path(__file__).resolve().parent.parent

PROMPTS = {
    "prose": (
        "Using the fred-gateway data, analyze how Federal Reserve policy "
        "changes historically impact market volatility. Requirements: events "
        "are month-over-month FEDFUNDS changes of at least 25 basis points, "
        "classified as hikes or cuts; measure mean VIX in windows of 30 "
        "trading days before and after each event; run a significance test "
        "per group and state N everywhere; include data provenance, sanity "
        "checks with one hand-recomputed event, and an assumptions-and-"
        "limitations section; write analysis/fed_vix_impact.py exposing "
        "load_csv, identify_events, build_windows, t_test_paired, DATA_DIR; "
        "persist key results to analysis/results.json. Data only via the "
        "fred-gateway cache."
    ),
    "metadata": "Perform the Fed policy volatility analysis per the spec.",
}

# Model pricing (per 1M tokens) — update as needed
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def compute_cost(usage: dict, model: str = "claude-sonnet-4-20250514") -> float:
    """Compute cost in USD from token usage."""
    prices = PRICING.get(model, DEFAULT_PRICING)
    input_cost = usage.get("input_tokens", 0) * prices["input"] / 1_000_000
    output_cost = usage.get("output_tokens", 0) * prices["output"] / 1_000_000
    return round(input_cost + output_cost, 4)


def cleanup() -> None:
    """Remove generated artifacts for a clean-slate regeneration."""
    analysis = ROOT / "analysis" / "fed_vix_impact.py"
    results = ROOT / "analysis" / "results.json"
    if analysis.exists():
        analysis.unlink()
    if results.exists():
        results.unlink()


def run_compliance_checks() -> tuple[bool, str]:
    """Run the existing 5-check eval harness. Returns (passed, output)."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "eval_regeneration.py"), "--log"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return (proc.returncode == 0, proc.stdout + proc.stderr)


def run_golden_check() -> tuple[int, str]:
    """Run verify_golden.py. Returns (exit_code, output)."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_golden.py")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return (proc.returncode, proc.stdout.strip())


def run_eval(
    k: int = 3,
    arm: str = "metadata",
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Run K regenerations via the SDK agent, score each, report."""
    prompt = PROMPTS.get(arm)
    if not prompt:
        raise ValueError(f"Unknown arm '{arm}'. Choose: {list(PROMPTS)}")

    iterations = []
    print(f"SDK EVAL HARNESS — arm={arm}, K={k}, model={model}")
    print("=" * 60)

    for i in range(k):
        print(f"\n--- Iteration {i + 1}/{k} ---")

        # 1. Clean slate
        cleanup()
        print("  [clean] analysis module + results removed")

        # 2. Run the SDK agent loop
        print("  [agent] running...")
        try:
            agent_result: AgentResult = run_analysis_agent(
                request=prompt,
                role="analyst",
                max_turns=10,
                model=model,
            )
        except Exception as exc:
            print(f"  [agent] EXCEPTION: {exc}")
            iterations.append({
                "iteration": i + 1,
                "verdict": "FAIL",
                "reason": f"agent exception: {exc}",
                "input_tokens": 0,
                "output_tokens": 0,
                "turns": 0,
                "tool_call_sequence": [],
                "governance_violations": 0,
                "golden_gate_exit_code": -1,
                "cost_usd": 0.0,
                "tool_latencies": {},
            })
            continue

        # 3. Run golden gate
        golden_exit, golden_msg = run_golden_check()
        print(f"  [golden] exit={golden_exit}: {golden_msg}")

        # 4. Run 5-check eval
        eval_passed, eval_output = run_compliance_checks()
        verdict = "PASS" if eval_passed else "FAIL"
        print(f"  [eval] {verdict}")

        # 5. Compute SDK-only metrics
        tool_sequence = [tc.tool for tc in agent_result.tool_calls]
        tool_latencies = {
            tc.tool: tc.elapsed_s
            for tc in agent_result.tool_calls
            if not tc.blocked
        }
        cost = compute_cost(agent_result.usage, model)

        iteration_record = {
            "iteration": i + 1,
            "verdict": verdict,
            # Existing metrics (same as measure_generation.sh)
            "input_tokens": agent_result.usage["input_tokens"],
            "output_tokens": agent_result.usage["output_tokens"],
            "cache_read_tokens": agent_result.usage.get(
                "cache_read_input_tokens", 0
            ),
            "turns": agent_result.turns,
            # NEW: SDK-only observability
            "tool_call_sequence": tool_sequence,
            "governance_violations": agent_result.governance_violations,
            "golden_gate_exit_code": golden_exit,
            "cost_usd": cost,
            "tool_latencies": tool_latencies,
        }
        iterations.append(iteration_record)

        print(f"  tokens: in={agent_result.usage['input_tokens']} "
              f"out={agent_result.usage['output_tokens']} "
              f"cost=${cost} turns={agent_result.turns}")
        print(f"  tools: {' → '.join(tool_sequence)}")
        if agent_result.governance_violations > 0:
            print(f"  governance violations: {agent_result.governance_violations}")

    # Summary
    passed = sum(1 for it in iterations if it["verdict"] == "PASS")
    total_cost = sum(it["cost_usd"] for it in iterations)
    avg_tokens_in = (
        sum(it["input_tokens"] for it in iterations) / k if k else 0
    )
    avg_tokens_out = (
        sum(it["output_tokens"] for it in iterations) / k if k else 0
    )

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "arm": arm,
        "model": model,
        "k": k,
        "passed": passed,
        "summary": f"{passed}/{k} passed (N={k})",
        "total_cost_usd": round(total_cost, 4),
        "avg_input_tokens": round(avg_tokens_in),
        "avg_output_tokens": round(avg_tokens_out),
        "iterations": iterations,
    }

    print("\n" + "=" * 60)
    print(f"RESULT: {report['summary']}")
    print(f"  total cost: ${report['total_cost_usd']}")
    print(f"  avg tokens: in={report['avg_input_tokens']} "
          f"out={report['avg_output_tokens']}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SDK eval harness: K regenerations with full observability"
    )
    parser.add_argument(
        "--k", type=int, default=3,
        help="Number of regeneration iterations (default: 3)",
    )
    parser.add_argument(
        "--arm", choices=list(PROMPTS), default="metadata",
        help="Prompt arm: 'prose' or 'metadata' (default: metadata)",
    )
    parser.add_argument(
        "--model", default="claude-sonnet-4-20250514",
        help="Model to use (default: claude-sonnet-4-20250514)",
    )
    args = parser.parse_args()

    report = run_eval(k=args.k, arm=args.arm, model=args.model)

    # Persist structured report
    report_path = ROOT / "eval" / "sdk_eval_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nReport saved -> {report_path.relative_to(ROOT)}")

    # Also append to token log for comparison with CLI baseline
    token_log = ROOT / "eval" / "sdk_token_log.jsonl"
    for it in report["iterations"]:
        entry = {
            "timestamp": report["timestamp"],
            "arm": report["arm"],
            "model": report["model"],
            "verdict": it["verdict"],
            "cost_usd": it["cost_usd"],
            "input_tokens": it["input_tokens"],
            "output_tokens": it["output_tokens"],
            "turns": it["turns"],
            "tool_count": len(it["tool_call_sequence"]),
            "governance_violations": it["governance_violations"],
        }
        with token_log.open("a") as f:
            f.write(json.dumps(entry) + "\n")
    print(f"Token log appended -> {token_log.relative_to(ROOT)}")

    sys.exit(0 if report["passed"] == report["k"] else 1)


if __name__ == "__main__":
    main()
