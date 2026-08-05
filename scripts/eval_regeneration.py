"""Regeneration eval: score one regenerated analysis against the shop's bar.

The determinism gate (verify_golden.py) answers "are the numbers exact?"
This harness answers the wider question: "did the generative layer land
a COMPLIANT analyst?" — five deterministic checks per regeneration,
scored pass/fail, no LLM judging anything.

Protocol for the measured claim:
  Run K fresh regenerations (fresh Claude Code session each — Session
  rule 1), run this after each, and report "K-of-K passed, N stated."
  Never say "100%" without saying K.

Usage:
  uv run python scripts/eval_regeneration.py            # score current state
  uv run python scripts/eval_regeneration.py --log      # append result to eval/regeneration_log.jsonl
"""

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS = ROOT / "analysis" / "fed_vix_impact.py"
RESULTS = ROOT / "analysis" / "results.json"
GOLDEN = ROOT / "data" / "seeds" / "golden_results.json"
LOG = ROOT / "eval" / "regeneration_log.jsonl"

REQUIRED_SYMBOLS = ["load_csv", "identify_events", "build_windows",
                    "t_test_paired", "DATA_DIR"]
# Textual obligations from the constitution — checked in the module
# source (docstring/output strings), case-insensitive.
REQUIRED_TEXT = ["limitation", "provenance", "sanity"]


def check(name: str, ok: bool, detail: str = "") -> dict:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return {"check": name, "passed": ok, "detail": detail}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args()

    print("REGENERATION EVAL")
    print("=" * 60)
    results = []

    # 1. Analysis module exists
    exists = ANALYSIS.exists()
    results.append(check("analysis module exists", exists, str(ANALYSIS.name)))

    # 2. Interface contract: the five symbols main.py imports
    if exists:
        spec = importlib.util.spec_from_file_location("fed_vix_impact", ANALYSIS)
        mod = importlib.util.module_from_spec(spec)
        try:
            # Import executes module top-level only (defs + constants);
            # analysis runs under __main__ guard, so this is cheap.
            spec.loader.exec_module(mod)
            missing = [s for s in REQUIRED_SYMBOLS if not hasattr(mod, s)]
            results.append(check("interface symbols", not missing,
                                 "all present" if not missing else f"missing: {missing}"))
        except Exception as exc:
            results.append(check("interface symbols", False, f"import failed: {exc}"))
    else:
        results.append(check("interface symbols", False, "no module"))

    # 3. Results artifact emitted
    results.append(check("results.json emitted", RESULTS.exists()))

    # 4. Determinism gate: reuse verify_golden as a subprocess so this
    #    harness and the gate can never drift apart.
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_golden.py")],
        capture_output=True, text=True,
    )
    results.append(check("golden verified", proc.returncode == 0,
                         proc.stdout.strip().splitlines()[-1] if proc.stdout else ""))

    # 5. Constitutional text obligations present in the analyst's source
    if exists:
        source = ANALYSIS.read_text().lower()
        missing_text = [t for t in REQUIRED_TEXT if t not in source]
        results.append(check("constitution text obligations", not missing_text,
                             "limitations/provenance/sanity present"
                             if not missing_text else f"missing: {missing_text}"))
    else:
        results.append(check("constitution text obligations", False, "no module"))

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    verdict = "PASS" if passed == total else "FAIL"
    print("=" * 60)
    print(f"REGENERATION {verdict}: {passed}/{total} checks")

    if args.log:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "verdict": verdict,
                "passed": passed,
                "total": total,
                "checks": results,
            }) + "\n")
        print(f"logged -> {LOG.relative_to(ROOT)}")

    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()