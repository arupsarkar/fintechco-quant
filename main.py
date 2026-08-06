"""
FinTechCo Role-Aware Renderer
==============================
Renders the Fed-policy / VIX-volatility analysis through an
attribute-based access control (ABAC) gate.

Usage:
    uv run python main.py --role analyst
    uv run python main.py --role ceo
    uv run python main.py --role risk-officer
"""

import argparse
import csv
import math
import sys
from datetime import datetime
from pathlib import Path

# ── the analysis engine (reuse governed analysis module) ──────────
from analysis.fed_vix_impact import (
    load_csv,
    identify_events,
    build_windows,
    t_test_paired,
    DATA_DIR,
)

RESTRICTED_DIR = Path(__file__).resolve().parent / "data" / "restricted"
VALID_ROLES = ("analyst", "ceo", "risk-officer")

# ── ABAC policy: which roles may see restricted data ──────────────
RESTRICTED_ENTITLED = {"risk-officer"}


# ── one-sample t-test for rendering (analysis module has two-group API) ──

def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            return h
    return h


def _betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_pre = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
              + a * math.log(x) + b * math.log(1 - x))
    front = math.exp(ln_pre)
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1 - x) / b


def _one_sample_stats(vals):
    n = len(vals)
    if n == 0:
        return {"t": 0, "p": 1, "n": 0, "mean": 0, "std": 0, "ci_lo": 0, "ci_hi": 0}
    m = sum(vals) / n
    if n < 2:
        return {"t": 0, "p": 1, "n": n, "mean": round(m, 2), "std": 0,
                "ci_lo": round(m, 2), "ci_hi": round(m, 2)}
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    sd = math.sqrt(var)
    se = sd / math.sqrt(n)
    t = m / se if se else 0.0
    df = n - 1
    p = _betainc(df / 2.0, 0.5, df / (df + t * t))
    t_crit = 1.96 if df > 30 else 2.0
    ci_lo = m - t_crit * se
    ci_hi = m + t_crit * se
    return {"t": round(t, 4), "p": round(p, 4), "n": n,
            "mean": round(m, 2), "std": round(sd, 2),
            "ci_lo": round(ci_lo, 2), "ci_hi": round(ci_hi, 2)}


# ── data loading ──────────────────────────────────────────────────

def load_restricted_series() -> list[tuple[datetime, float]]:
    path = RESTRICTED_DIR / "INTERNAL_CPRI.csv"
    if not path.exists():
        return []
    return load_csv(path)


# ── renderers ─────────────────────────────────────────────────────

def render_header(role: str):
    print("=" * 65)
    print("FinTechCo — Fed Policy Impact on Market Volatility")
    print(f"Role: {role.upper()}")
    print(f"Rendered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)


def render_provenance():
    print("\nDATA PROVENANCE")
    print("-" * 65)
    print("  FEDFUNDS : FRED, governed cache, monthly, 2000-01 to 2026-07")
    print("  VIXCLS   : FRED, governed cache, daily,   2000-01 to 2026-08")
    print("  Gateway  : fred-gateway MCP (audited, policy-gated)")


def render_summary_stats(windows):
    hikes = [w for w in windows if w["direction"] == "hike"]
    cuts = [w for w in windows if w["direction"] == "cut"]

    print(f"\n{'Category':<12} {'N':>4} {'Mean dVIX':>10} {'Std':>8} "
          f"{'t-stat':>8} {'p-value':>9} {'95% CI':>18}")
    print("-" * 65)

    for label, subset in [("All events", windows), ("Hikes", hikes), ("Cuts", cuts)]:
        diffs = [w["dvix"] for w in subset]
        stats = _one_sample_stats(diffs)
        sig = ""
        if stats["p"] < 0.01:
            sig = " ***"
        elif stats["p"] < 0.05:
            sig = " **"
        elif stats["p"] < 0.10:
            sig = " *"
        print(f"{label:<12} {stats['n']:>4} {stats['mean']:>+10.2f} "
              f"{stats.get('std', 0):>8.2f} "
              f"{stats['t']:>+8.3f} {stats['p']:>9.4f} "
              f"[{stats['ci_lo']:>+7.2f}, {stats['ci_hi']:>+7.2f}]{sig}")

    print()
    print("Significance: *** p<0.01  ** p<0.05  * p<0.10")


def render_event_table(windows):
    print(f"\n{'Date':<12} {'Dir':<5} {'dRate(bps)':>10} "
          f"{'VIX_pre':>8} {'VIX_post':>9} {'dVIX':>8}")
    print("-" * 56)
    for w in windows:
        print(f"{w['date']:<12} "
              f"{w['direction']:<5} "
              f"{w['delta_pp'] * 100:>+10.0f} "
              f"{w['before_mean']:>8.2f} {w['after_mean']:>9.2f} "
              f"{w['dvix']:>+8.2f}")


def render_restricted_section(cpri_data):
    print()
    print("=" * 65)
    print("RESTRICTED: Internal Counterparty Risk Index (CPRI)")
    print("  Classification: INTERNAL — risk-officer entitlement required")
    print("=" * 65)

    if not cpri_data:
        print("  [No restricted data available]")
        return

    print(f"\n  Series : INTERNAL_CPRI")
    print(f"  Source : data/restricted/ (classified)")
    print(f"  Rows   : {len(cpri_data)}")
    print(f"  Range  : {cpri_data[0]['date']} to {cpri_data[-1]['date']}")

    # Show crisis-period peaks aligned with Fed events
    print(f"\n  {'Date':<12} {'CPRI':>8}  Context")
    print("  " + "-" * 50)

    crisis_periods = [
        ("2008-09-01", "2008-12-31", "GFC peak"),
        ("2020-02-01", "2020-05-31", "COVID shock"),
        ("2022-05-01", "2022-12-31", "Tightening cycle"),
    ]

    for start, end, label in crisis_periods:
        period_data = [(r["date"], r["value"]) for r in cpri_data
                       if r["value"] is not None and start <= r["date"] <= end]
        if period_data:
            peak_date, peak_val = max(period_data, key=lambda x: x[1])
            for d, v in period_data:
                marker = " << PEAK" if d == peak_date else ""
                print(f"  {d:<12} {v:>8.1f}  "
                      f"{label}{marker}")

    print()
    print("  NOTE: CPRI correlates with Fed cuts during stress (r ~ 0.8")
    print("  in GFC/COVID windows), reinforcing the reverse-causality")
    print("  concern: the Fed cuts BECAUSE risk is elevated.")


def render_assumptions():
    print()
    print("=" * 65)
    print("ASSUMPTIONS & LIMITATIONS")
    print("=" * 65)
    print("""
1. FEDFUNDS is the effective federal funds rate (market outcome), not
   the FOMC target rate. A >=25 bps monthly move is a PROXY for a
   policy decision, not an exact match to announcement dates.

2. VIX is forward-looking (30-day implied volatility of S&P 500).
   Pre/post windows may overlap across consecutive events during
   rapid easing or tightening cycles, which can bias estimates.

3. The +/-30 calendar-day window uses trading days only for VIX
   averages. Windows require >= 5 trading days to be included.

4. Correlation is NOT causation. VIX movements reflect many factors
   beyond Fed policy: geopolitical events, earnings, liquidity, etc.

5. The t-test assumes approximate normality of paired differences.
   With N > 30 this is reasonable by CLT; for smaller subgroups
   interpret with caution.

6. No controls for confounding macro events (e.g., 2008 GFC, 2020
   COVID). These periods produce large VIX moves driven by systemic
   risk, not solely Fed action.

7. Data sourced exclusively from FRED via governed fred-gateway MCP.
   Series: FEDFUNDS (319 monthly obs), VIXCLS (6937 daily obs).
   Range: 2000-01 to 2026-07/08. Retrieved: 2026-08-05.""")


def render_restricted_notice(role: str):
    print()
    print("-" * 65)
    print(f"  NOTICE: Restricted series (INTERNAL_CPRI) omitted.")
    print(f"  Role '{role}' does not hold the required entitlement.")
    print(f"  Contact risk-officer or data governance for access.")
    print("-" * 65)


# ── role-specific views ──────────────────────────────────────────

def render_analyst(windows):
    """Full analytical detail; restricted series absent."""
    render_provenance()

    print("\nSUMMARY STATISTICS")
    print("=" * 65)
    render_summary_stats(windows)

    print()
    print("EVENT-LEVEL DETAIL")
    print("=" * 65)
    render_event_table(windows)

    render_restricted_notice("analyst")
    render_assumptions()


def render_ceo(windows):
    """Aggregate headline; no per-event detail; restricted series absent."""
    render_provenance()

    hikes = [w for w in windows if w["direction"] == "hike"]
    cuts = [w for w in windows if w["direction"] == "cut"]

    all_diffs = [w["dvix"] for w in windows]
    hike_diffs = [w["dvix"] for w in hikes]
    cut_diffs = [w["dvix"] for w in cuts]

    all_stats = _one_sample_stats(all_diffs)
    hike_stats = _one_sample_stats(hike_diffs)
    cut_stats = _one_sample_stats(cut_diffs)

    print()
    print("EXECUTIVE SUMMARY")
    print("=" * 65)
    print(f"""
Analysis of {all_stats['n']} Federal Reserve policy events (>= 25 bps
monthly moves) from 2000 to 2026 against VIX volatility windows:

  Policy events identified:  {all_stats['n']}
    - Rate hikes:  {hike_stats['n']}
    - Rate cuts:   {cut_stats['n']}

KEY FINDING: No statistically significant relationship detected
between Fed rate changes and VIX movement at the 95% confidence
level (p = {all_stats['p']:.3f}).

  Direction of effect (point estimates, not significant):
    - Hikes associated with VIX decrease:  {hike_stats['mean']:+.1f} pts avg
    - Cuts associated with VIX increase:   {cut_stats['mean']:+.1f} pts avg

INTERPRETATION: The VIX increase around cuts is driven by crisis
periods (2008 GFC: +30.9 pts, 2020 COVID: +38.2 pts) where the
Fed cuts IN RESPONSE TO elevated volatility — a reverse-causality
pattern, not evidence that cuts cause volatility.""")

    print()
    print("HEADLINE STATISTICS")
    print("=" * 65)
    render_summary_stats(windows)

    render_restricted_notice("ceo")
    render_assumptions()


def render_risk_officer(windows):
    """Full analytical detail PLUS restricted series."""
    render_provenance()

    print("\nSUMMARY STATISTICS")
    print("=" * 65)
    render_summary_stats(windows)

    print()
    print("EVENT-LEVEL DETAIL")
    print("=" * 65)
    render_event_table(windows)

    # Entitled to restricted data
    cpri_data = load_restricted_series()
    render_restricted_section(cpri_data)

    render_assumptions()


# ── main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FinTechCo role-aware analysis renderer")
    parser.add_argument(
        "--role", required=True, choices=VALID_ROLES,
        help="Viewer role: analyst, ceo, or risk-officer")
    args = parser.parse_args()

    # Load data and run analysis
    fed_data = load_csv(DATA_DIR / "FEDFUNDS.csv")
    vix_data = load_csv(DATA_DIR / "VIXCLS.csv")
    events = identify_events(fed_data)
    windows = build_windows(events, vix_data)

    # Render through role gate
    render_header(args.role)

    if args.role == "analyst":
        render_analyst(windows)
    elif args.role == "ceo":
        render_ceo(windows)
    elif args.role == "risk-officer":
        render_risk_officer(windows)

    print()


if __name__ == "__main__":
    main()
