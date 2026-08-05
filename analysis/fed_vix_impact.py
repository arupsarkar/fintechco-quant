"""
Fed Policy -> VIX Impact Analysis
=================================
Quantifies how Federal Reserve policy changes (>=25 bps monthly moves
in the effective federal funds rate) affect S&P 500 implied volatility
(VIX) in +-30-day windows around each event.

Data provenance
---------------
  FEDFUNDS : FRED series, governed cache, monthly, 2000-01 -> 2026-07
  VIXCLS   : FRED series, governed cache, daily,   2000-01 -> 2026-08
  Gateway  : fred-gateway MCP (audited, policy-gated)
  Retrieved: 2026-08-05
"""

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, stdev

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


# -- data structures ----------------------------------------------------------

@dataclass
class Event:
    date: datetime
    direction: str   # "hike" or "cut"
    delta: float     # change in percentage points (e.g. 0.50 = 50 bps)


@dataclass
class Window:
    event: Event
    vix_pre: float   # mean VIX in 30 calendar days before event
    vix_post: float  # mean VIX in 30 calendar days after event
    delta_vix: float # vix_post - vix_pre


# -- CSV loader ---------------------------------------------------------------

def load_csv(path) -> list[tuple[datetime, float]]:
    """Parse a FRED-style date,value CSV.  Skips non-numeric values."""
    rows: list[tuple[datetime, float]] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            try:
                dt = datetime.strptime(row[0], "%Y-%m-%d")
                val = float(row[1])
                rows.append((dt, val))
            except (ValueError, IndexError):
                continue
    rows.sort(key=lambda r: r[0])
    return rows


# -- event identification -----------------------------------------------------

def identify_events(fed_data: list[tuple[datetime, float]]) -> list[Event]:
    """Detect months with >=25 bps change in effective fed funds rate."""
    events: list[Event] = []
    for i in range(1, len(fed_data)):
        _, prev_val = fed_data[i - 1]
        curr_date, curr_val = fed_data[i]
        delta = curr_val - prev_val
        if abs(delta) >= 0.25:
            direction = "hike" if delta > 0 else "cut"
            events.append(Event(date=curr_date, direction=direction,
                                delta=delta))
    return events


# -- window builder -----------------------------------------------------------

def build_windows(events: list[Event],
                  vix_data: list[tuple[datetime, float]]) -> list[Window]:
    """Build +-30-day VIX comparison windows around each event.

    Uses trading days only (dates present in vix_data).
    Requires >=5 trading days in each half-window.
    """
    vix_by_date: dict[datetime, float] = {d: v for d, v in vix_data}
    vix_dates = sorted(vix_by_date)

    windows: list[Window] = []
    for ev in events:
        pre_start = ev.date - timedelta(days=30)
        pre_end = ev.date - timedelta(days=1)
        post_start = ev.date + timedelta(days=1)
        post_end = ev.date + timedelta(days=30)

        pre_vals = [vix_by_date[d] for d in vix_dates
                    if pre_start <= d <= pre_end]
        post_vals = [vix_by_date[d] for d in vix_dates
                     if post_start <= d <= post_end]

        if len(pre_vals) >= 5 and len(post_vals) >= 5:
            vix_pre = mean(pre_vals)
            vix_post = mean(post_vals)
            windows.append(Window(
                event=ev,
                vix_pre=vix_pre,
                vix_post=vix_post,
                delta_vix=vix_post - vix_pre,
            ))
    return windows


# -- t-distribution helpers (stdlib only, no scipy) ---------------------------

def _log_beta(a: float, b: float) -> float:
    return math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for regularised incomplete beta (Lentz)."""
    max_iter, eps = 200, 3.0e-12
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        # odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lf = a * math.log(x) + b * math.log(1.0 - x) - _log_beta(a, b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lf) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lf) * _betacf(b, a, 1.0 - x) / b


def _t_pvalue_two(t_val: float, df: int) -> float:
    """Two-tailed p-value from the t-distribution."""
    if df <= 0:
        return 1.0
    x = df / (df + t_val * t_val)
    return _betainc(df / 2.0, 0.5, x)


def _t_critical(alpha: float, df: int) -> float:
    """Critical |t| for a two-tailed test at level *alpha*, via bisection."""
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _betainc(df / 2.0, 0.5, df / (df + mid * mid)) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# -- paired t-test ------------------------------------------------------------

def t_test_paired(diffs: list[float]) -> dict:
    """One-sample t-test on paired differences (H0: mean = 0).

    Returns dict with keys: n, mean, std, t, p, ci_lo, ci_hi.
    """
    n = len(diffs)
    if n == 0:
        return {"n": 0, "mean": 0.0, "std": 0.0,
                "t": 0.0, "p": 1.0, "ci_lo": 0.0, "ci_hi": 0.0}
    if n == 1:
        m = diffs[0]
        return {"n": 1, "mean": m, "std": 0.0,
                "t": 0.0, "p": 1.0, "ci_lo": m, "ci_hi": m}

    m = mean(diffs)
    s = stdev(diffs)
    se = s / math.sqrt(n)
    t_stat = m / se if se > 0 else 0.0
    df = n - 1
    p = _t_pvalue_two(t_stat, df)
    t_crit = _t_critical(0.05, df)
    ci_lo = m - t_crit * se
    ci_hi = m + t_crit * se
    return {"n": n, "mean": m, "std": s,
            "t": t_stat, "p": p, "ci_lo": ci_lo, "ci_hi": ci_hi}


# -- results persistence ------------------------------------------------------

RESULTS_PATH = Path(__file__).resolve().parent / "results.json"


def _hand_check_delta(fed_data: list[tuple[datetime, float]],
                      year: int, month: int) -> float:
    """Hand-method spot-check: subtract consecutive raw values."""
    for i, (d, v) in enumerate(fed_data):
        if d.year == year and d.month == month and i > 0:
            return round(v - fed_data[i - 1][1], 2)
    raise ValueError(f"FEDFUNDS {year}-{month:02d} not found for hand check")


def _persist_results(windows: list[Window],
                     fed_data: list[tuple[datetime, float]]) -> None:
    """Write key results to analysis/results.json."""
    hike_diffs = [w.delta_vix for w in windows if w.event.direction == "hike"]
    cut_diffs = [w.delta_vix for w in windows if w.event.direction == "cut"]
    all_stats = t_test_paired([w.delta_vix for w in windows])
    hike_stats = t_test_paired(hike_diffs)
    cut_stats = t_test_paired(cut_diffs)

    results = {
        "n_events":                   all_stats["n"],
        "n_hikes":                    hike_stats["n"],
        "n_cuts":                     cut_stats["n"],
        "mean_dvix_all":              round(all_stats["mean"], 2),
        "mean_dvix_hikes":            round(hike_stats["mean"], 2),
        "mean_dvix_cuts":             round(cut_stats["mean"], 2),
        "hand_check_mar2020_delta_pp": _hand_check_delta(fed_data, 2020, 3),
        "hand_check_jun2022_delta_pp": _hand_check_delta(fed_data, 2022, 6),
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")
    print(f"  Results persisted to {RESULTS_PATH}")


# -- sanity checks (run when executed directly) -------------------------------

def _sanity_check():
    """Verify date alignment, spot-check a known event, and state N."""
    print("SANITY CHECKS")
    print("=" * 60)

    fed = load_csv(DATA_DIR / "FEDFUNDS.csv")
    vix = load_csv(DATA_DIR / "VIXCLS.csv")

    # 1. FEDFUNDS date alignment — should be monthly with no gaps
    gaps = []
    for i in range(1, len(fed)):
        prev_d, curr_d = fed[i - 1][0], fed[i][0]
        diff_days = (curr_d - prev_d).days
        if diff_days < 28 or diff_days > 31:
            gaps.append((prev_d.date(), curr_d.date(), diff_days))
    if gaps:
        print(f"  WARNING: {len(gaps)} date gap(s) in FEDFUNDS:")
        for g in gaps[:5]:
            print(f"    {g[0]} -> {g[1]} ({g[2]} days)")
    else:
        print(f"  FEDFUNDS date alignment: OK (monthly, {len(fed)} obs)")

    # 2. VIX coverage
    print(f"  VIXCLS: {len(vix)} trading days, "
          f"{vix[0][0].date()} -> {vix[-1][0].date()}")

    # 3. Identify events and state N
    events = identify_events(fed)
    hikes = [e for e in events if e.direction == "hike"]
    cuts = [e for e in events if e.direction == "cut"]
    print(f"  Events: {len(events)} total "
          f"({len(hikes)} hikes, {len(cuts)} cuts)")

    # 4. Spot-check: Oct 2008 emergency cut
    #    FEDFUNDS fell sharply Sep -> Oct 2008
    oct_events = [e for e in events
                  if e.date.year == 2008 and e.date.month == 10]
    if oct_events:
        e = oct_events[0]
        print(f"  Spot-check Oct 2008: direction={e.direction}, "
              f"delta={e.delta:+.2f} ({e.delta * 100:+.0f} bps)")
        sep08 = [v for d, v in fed if d.year == 2008 and d.month == 9]
        oct08 = [v for d, v in fed if d.year == 2008 and d.month == 10]
        if sep08 and oct08:
            raw_delta = oct08[0] - sep08[0]
            match = "MATCH" if abs(raw_delta - e.delta) < 0.005 else "MISMATCH"
            print(f"    Raw: Sep={sep08[0]:.2f}, Oct={oct08[0]:.2f}, "
                  f"delta={raw_delta:+.2f} -- {match}")
    else:
        print("  Spot-check Oct 2008: event not found (unexpected)")

    # 5. Build windows and report coverage
    windows = build_windows(events, vix)
    w_hikes = [w for w in windows if w.event.direction == "hike"]
    w_cuts = [w for w in windows if w.event.direction == "cut"]
    print(f"  Windows built: {len(windows)} "
          f"({len(w_hikes)} hikes, {len(w_cuts)} cuts; "
          f"dropped {len(events) - len(windows)} for <5 trading days)")

    # 6. Persist results to analysis/results.json
    _persist_results(windows, fed)

    # 7. t-test numerical check — constant input should be degenerate
    test = t_test_paired([1.0, 1.0, 1.0])
    ok = "OK (degenerate)" if test["t"] == 0.0 and test["p"] == 1.0 else "CHECK"
    print(f"  t-test constant input: t={test['t']:.1f}, p={test['p']:.1f} -- {ok}")

    # 8. t-test cross-check — known values
    #    For [2, 4, 6]: mean=4, std=2, se=2/sqrt(3)=1.1547, t=4/1.1547=3.464
    #    df=2, two-tailed p ≈ 0.0742
    test2 = t_test_paired([2.0, 4.0, 6.0])
    p_ok = "OK" if abs(test2["p"] - 0.0742) < 0.01 else "CHECK"
    print(f"  t-test [2,4,6]: t={test2['t']:.3f}, p={test2['p']:.4f} -- {p_ok}")

    print("=" * 60)


if __name__ == "__main__":
    _sanity_check()
