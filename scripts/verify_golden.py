"""Determinism check: current results must reproduce the golden numbers.

The agent regenerates the ANALYST (code) each demo; frozen data +
explicit rules mean the ANSWERS must not change. Exit 0 = verified.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOLERANCE = 0.01   # floats reported at 2dp

golden = json.loads((ROOT / "data/seeds/golden_results.json").read_text())
results = json.loads((ROOT / "analysis/results.json").read_text())

failures = []
for key, expected in golden.items():
    actual = results.get(key)
    if actual is None:
        failures.append(f"{key}: MISSING from results")
    elif isinstance(expected, float) and abs(actual - expected) > TOLERANCE:
        failures.append(f"{key}: expected {expected}, got {actual}")
    elif isinstance(expected, int) and actual != expected:
        failures.append(f"{key}: expected {expected}, got {actual}")

if failures:
    print("GOLDEN MISMATCH:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)

print(f"GOLDEN VERIFIED: {len(golden)} values reproduced (tolerance {TOLERANCE})")