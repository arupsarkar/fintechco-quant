"""Fed policy volatility analysis — implements spec/analysis_spec.json."""

import csv
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"


def load_csv(filename: str) -> list[dict]:
    """Load a date/value CSV from the governed data cache."""
    path = DATA_DIR / filename
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            val = None if row["value"] == "." else float(row["value"])
            rows.append({"date": row["date"], "value": val})
    return rows


def identify_events(fedfunds: list[dict]) -> list[dict]:
    """Find months where the fed-funds rate changed >= 25 bps MoM."""
    events = []
    for i in range(1, len(fedfunds)):
        delta = round(fedfunds[i]["value"] - fedfunds[i - 1]["value"], 2)
        if abs(delta) >= 0.25:
            events.append({
                "date": fedfunds[i]["date"],
                "delta_pp": delta,
                "direction": "hike" if delta > 0 else "cut",
            })
    return events


def build_windows(events: list[dict], vix: list[dict]) -> list[dict]:
    """Attach 30-calendar-day before/after VIX windows and delta to each event.

    Uses calendar-day windows (timedelta 30 days) over valid VIX
    observations.  Event date itself is excluded from both windows.
    """
    vix_parsed = []
    for r in vix:
        if r["value"] is not None:
            vix_parsed.append((datetime.strptime(r["date"], "%Y-%m-%d"), r["value"]))
    result = []
    for ev in events:
        edate = datetime.strptime(ev["date"], "%Y-%m-%d")
        w_start = edate - timedelta(days=30)
        w_end = edate + timedelta(days=30)
        before = [v for d, v in vix_parsed if w_start <= d < edate]
        after = [v for d, v in vix_parsed if edate < d <= w_end]
        if not before or not after:
            continue
        bm = sum(before) / len(before)
        am = sum(after) / len(after)
        result.append({
            **ev,
            "before_mean": round(bm, 2),
            "after_mean": round(am, 2),
            "dvix": round(am - bm, 2),
        })
    return result


# -- t-distribution helpers (stdlib only) --

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


def t_test_paired(deltas_a: list[float], deltas_b: list[float]) -> dict:
    """One-sample t-tests: is each group's mean VIX delta significantly != 0?"""
    def _one_sample(vals):
        n = len(vals)
        m = sum(vals) / n
        var = sum((x - m) ** 2 for x in vals) / (n - 1)
        se = math.sqrt(var / n)
        t = m / se if se else 0.0
        df = n - 1
        p = _betainc(df / 2.0, 0.5, df / (df + t * t))
        return {"t_stat": round(t, 4), "p_value": round(p, 4), "n": n}

    return {"hikes": _one_sample(deltas_a), "cuts": _one_sample(deltas_b)}


# -- main --

if __name__ == "__main__":
    ts = datetime.now(timezone.utc).isoformat()
    fedfunds = load_csv("FEDFUNDS.csv")
    vix = load_csv("VIXCLS.csv")

    print("=" * 60)
    print("FED POLICY -> VOLATILITY ANALYSIS")
    print("=" * 60)
    print(f"\nPROVENANCE")
    print(f"  Source   : FRED via fred-gateway governed cache")
    print(f"  FEDFUNDS : {fedfunds[0]['date']} to {fedfunds[-1]['date']} ({len(fedfunds)} months)")
    vix_valid = [v for v in vix if v["value"] is not None]
    print(f"  VIXCLS   : {vix[0]['date']} to {vix[-1]['date']} ({len(vix_valid)} trading days)")
    print(f"  Retrieved: {ts}")

    events = identify_events(fedfunds)
    windowed = build_windows(events, vix)
    hikes = [e for e in windowed if e["direction"] == "hike"]
    cuts = [e for e in windowed if e["direction"] == "cut"]

    all_dv = [e["dvix"] for e in windowed]
    hk_dv = [e["dvix"] for e in hikes]
    ct_dv = [e["dvix"] for e in cuts]

    n_ev, n_hk, n_ct = len(windowed), len(hikes), len(cuts)
    m_all = round(sum(all_dv) / n_ev, 2)
    m_hk = round(sum(hk_dv) / n_hk, 2)
    m_ct = round(sum(ct_dv) / n_ct, 2)

    print(f"\nRESULTS (N={n_ev}: {n_hk} hikes, {n_ct} cuts)")
    print(f"  Mean dVIX overall : {m_all:+.2f}")
    print(f"  Mean dVIX hikes   : {m_hk:+.2f}  (N={n_hk})")
    print(f"  Mean dVIX cuts    : {m_ct:+.2f}  (N={n_ct})")

    tt = t_test_paired(hk_dv, ct_dv)
    print(f"  Hikes: t={tt['hikes']['t_stat']:.3f}, p={tt['hikes']['p_value']:.4f} (N={tt['hikes']['n']})")
    print(f"  Cuts:  t={tt['cuts']['t_stat']:.3f}, p={tt['cuts']['p_value']:.4f} (N={tt['cuts']['n']})")

    # -- sanity checks --
    print("\nSANITY CHECKS")
    assert all(d["date"].endswith("-01") for d in fedfunds), "FEDFUNDS not month-starts"
    print("  [ok] FEDFUNDS dates are month-starts")
    sample = [datetime.strptime(v["date"], "%Y-%m-%d") for v in vix_valid[:100]]
    assert all(d.weekday() < 5 for d in sample), "Weekend dates in VIX"
    print("  [ok] VIX dates are trading days (no weekends)")

    mar20 = next((e["delta_pp"] for e in events if e["date"] == "2020-03-01"), None)
    jun22 = next((e["delta_pp"] for e in events if e["date"] == "2022-06-01"), None)
    print(f"  Hand-check Mar-2020 delta: {mar20} pp")
    print(f"  Hand-check Jun-2022 delta: {jun22} pp")

    # -- persist results --
    results = {
        "n_events": n_ev, "n_hikes": n_hk, "n_cuts": n_ct,
        "mean_dvix_all": m_all, "mean_dvix_hikes": m_hk, "mean_dvix_cuts": m_ct,
        "hand_check_mar2020_delta_pp": mar20,
        "hand_check_jun2022_delta_pp": jun22,
    }
    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n  [ok] Results persisted -> {out}")

    print("\nASSUMPTIONS & LIMITATIONS")
    print("  1. Correlation != causation: VIX shifts may reflect broader macro")
    print("     conditions, not the rate decision itself.")
    print("  2. VIX is forward-looking (expected 30-day vol); markets may price")
    print("     anticipated moves before the FEDFUNDS print.")
    print("  3. Window overlap possible for consecutive events <60 trading days apart.")
    print("  4. Event date = 1st of month, not actual FOMC meeting date.")
    print("  5. Threshold of 25 bps may miss smaller but policy-relevant moves.")
    print("=" * 60)
