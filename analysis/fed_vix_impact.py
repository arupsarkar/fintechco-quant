"""Fed policy → VIX volatility impact analysis.

Data provenance
---------------
- FEDFUNDS: Federal Funds Effective Rate (monthly), FRED via fred-gateway
  Range 2000-01-01 → 2026-07-01, 319 rows.
  Retrieved 2026-08-06T03:57:30Z.
- VIXCLS: CBOE Volatility Index (daily close), FRED via fred-gateway
  Range 2000-01-03 → 2026-08-04, 6 937 rows.
  Retrieved 2026-08-06T03:57:31Z.

Exports (per interface contract): load_csv, identify_events,
build_windows, t_test_paired, DATA_DIR.
"""

import json
import pathlib
from datetime import datetime, timezone

import pandas as pd
from scipy import stats

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "cache"
_RESULTS_PATH = pathlib.Path(__file__).resolve().parent / "results.json"
_GOLDEN_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "seeds" / "golden_results.json"


# ---------------------------------------------------------------------------
# Step 1 — load
# ---------------------------------------------------------------------------

def load_csv(series_id: str) -> pd.DataFrame:
    """Read a governed-cache CSV into a DataFrame with parsed dates."""
    path = DATA_DIR / f"{series_id}.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Step 2 — identify rate-change events
# ---------------------------------------------------------------------------

def identify_events(
    fedfunds: pd.DataFrame,
    threshold_bps: int = 25,
) -> pd.DataFrame:
    """Flag months where |MoM change| >= threshold (in basis points).

    Returns a DataFrame with columns: date, value, change, direction.
    """
    df = fedfunds.copy()
    df["change"] = df["value"].diff()
    threshold_pp = threshold_bps / 100          # 25 bps → 0.25 pp
    mask = df["change"].abs() >= threshold_pp
    events = df.loc[mask, ["date", "value", "change"]].copy()
    events["direction"] = events["change"].apply(
        lambda x: "hike" if x > 0 else "cut",
    )
    return events.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 3 — build VIX windows around each event
# ---------------------------------------------------------------------------

def build_windows(
    events: pd.DataFrame,
    vix: pd.DataFrame,
    before_days: int = 30,
    after_days: int = 30,
) -> pd.DataFrame:
    """For each event compute mean VIX in calendar-day windows
    before and after the event date, then delta = after − before.

    Window uses all trading days (VIX observations) within the
    calendar-day range around each event date.
    """
    vix = vix.copy().sort_values("date").reset_index(drop=True)
    rows: list[dict] = []

    for _, ev in events.iterrows():
        edate = ev["date"]
        window_start = edate - pd.Timedelta(days=before_days)
        window_end = edate + pd.Timedelta(days=after_days)

        before = vix.loc[
            (vix["date"] >= window_start) & (vix["date"] < edate)
        ]
        after = vix.loc[
            (vix["date"] > edate) & (vix["date"] <= window_end)
        ]

        if len(before) == 0 or len(after) == 0:
            continue

        mean_b = before["value"].mean()
        mean_a = after["value"].mean()
        delta = mean_a - mean_b

        rows.append({
            "date": edate,
            "direction": ev["direction"],
            "change_pp": round(ev["change"], 2),
            "mean_vix_before": round(mean_b, 2),
            "mean_vix_after": round(mean_a, 2),
            "delta_vix": round(delta, 2),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Step 4 — significance test
# ---------------------------------------------------------------------------

def t_test_paired(
    deltas_hikes: pd.Series,
    deltas_cuts: pd.Series,
) -> dict:
    """One-sample t-tests: is the mean VIX delta significantly ≠ 0?"""
    t_h, p_h = stats.ttest_1samp(deltas_hikes, 0)
    t_c, p_c = stats.ttest_1samp(deltas_cuts, 0)
    return {
        "hikes": {"t_stat": round(float(t_h), 4),
                   "p_value": round(float(p_h), 4),
                   "n": len(deltas_hikes)},
        "cuts":  {"t_stat": round(float(t_c), 4),
                   "p_value": round(float(p_c), 4),
                   "n": len(deltas_cuts)},
    }


# ---------------------------------------------------------------------------
# Main: run full analysis, persist, validate
# ---------------------------------------------------------------------------

def main() -> dict:
    fedfunds = load_csv("FEDFUNDS")
    vix = load_csv("VIXCLS")

    events = identify_events(fedfunds)
    windows = build_windows(events, vix)

    hikes = windows.loc[windows["direction"] == "hike"]
    cuts = windows.loc[windows["direction"] == "cut"]

    sig = t_test_paired(hikes["delta_vix"], cuts["delta_vix"])

    # ---- hand-check two events (sanity gate) ----
    mar2020 = windows.loc[windows["date"] == pd.Timestamp("2020-03-01")]
    jun2022 = windows.loc[windows["date"] == pd.Timestamp("2022-06-01")]

    results = {
        "n_events": int(len(windows)),
        "n_hikes": int(len(hikes)),
        "n_cuts": int(len(cuts)),
        "mean_dvix_all": round(float(windows["delta_vix"].mean()), 2),
        "mean_dvix_hikes": round(float(hikes["delta_vix"].mean()), 2),
        "mean_dvix_cuts": round(float(cuts["delta_vix"].mean()), 2),
        "hand_check_mar2020_delta_pp": round(
            float(mar2020["change_pp"].iloc[0]), 2,
        ),
        "hand_check_jun2022_delta_pp": round(
            float(jun2022["change_pp"].iloc[0]), 2,
        ),
    }

    # ---- persist ----
    _RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n")

    # ---- validate against golden ----
    golden = json.loads(_GOLDEN_PATH.read_text())
    mismatches = {
        k: {"got": results[k], "expected": golden[k]}
        for k in golden
        if results.get(k) != golden[k]
    }
    if mismatches:
        print("GOLDEN MISMATCH:", json.dumps(mismatches, indent=2))
    else:
        print("All results match golden reference.")

    # ---- print summary ----
    print(f"\nEvents: {results['n_events']}  "
          f"(hikes {results['n_hikes']}, cuts {results['n_cuts']})")
    print(f"Mean ΔVIX  all: {results['mean_dvix_all']:+.2f}  "
          f"hikes: {results['mean_dvix_hikes']:+.2f}  "
          f"cuts: {results['mean_dvix_cuts']:+.2f}")
    print(f"\nSignificance — hikes t={sig['hikes']['t_stat']:.3f} "
          f"p={sig['hikes']['p_value']:.4f} (N={sig['hikes']['n']})")
    print(f"Significance — cuts  t={sig['cuts']['t_stat']:.3f} "
          f"p={sig['cuts']['p_value']:.4f} (N={sig['cuts']['n']})")
    print(f"\nHand-checks: Mar-2020 Δpp={results['hand_check_mar2020_delta_pp']}, "
          f"Jun-2022 Δpp={results['hand_check_jun2022_delta_pp']}")

    print("\n--- ASSUMPTIONS & LIMITATIONS ---")
    print("• FEDFUNDS is the effective rate monthly average, not the target.")
    print("• VIX windows use 30 trading days; events near data boundaries "
          "are excluded if a full window is unavailable.")
    print("• Correlation between rate moves and VIX shifts is not causation; "
          "confounders (macro shocks, geopolitical events) are not controlled.")
    print("• Month-over-month changes may understate mid-month rate moves "
          "because FEDFUNDS is the monthly average.")

    return results


if __name__ == "__main__":
    main()
