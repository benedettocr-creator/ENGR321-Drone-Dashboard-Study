"""Paired t-tests comparing Nimbus Express and AeroDash, straight from the sim's CSVs.

This is a reproducible cross-check of the 5_Stats tab in
Project2_Analysis_Workbook.xlsx. It reads, under data/raw/<ParticipantID>/:

  *_summary.csv        one row per flight, written by drone_sim.html
  *_survey.csv         NASA-TLX and SUS answers after each flight
  *_heart_rate.csv     mean heart rate per window (tools/ingest.py hr)

Run from the repository root to print the tables:
    python analysis/analyze.py

tools/build_report.py imports these functions to build the report.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

DASHBOARDS = ("Nimbus", "AeroDash")
DASHBOARD_NAMES = {"Nimbus": "Nimbus Express", "AeroDash": "AeroDash"}
TRIALS = ("Trial1", "Trial2")

# (column, label, unit, which direction is better) in the order of the 5_Stats tab
MEASURES = [
    ("MeanAlertRT_s", "Mean alert reaction time", "s", "lower"),
    ("LowBatt_TimeToCharge_s", "Low-battery time to charge", "s", "lower"),
    ("Wind_TimeToDescend_s", "Wind time to descend", "s", "lower"),
    ("MissedAlerts", "Missed alerts", "count", "lower"),
    ("GatesPassed", "Gates passed (of 15)", "count", "higher"),
    ("Collisions", "Collisions", "count", "lower"),
    ("MeanPathDeviation_m", "Path deviation", "m", "lower"),
    ("TaskTime_s", "Task time", "s", "lower"),
    ("HR_change_bpm", "Heart rate change from rest", "bpm", "lower"),
    ("NASA_TLX_raw", "NASA-TLX (raw)", "0-100", "lower"),
    ("SUS_score", "SUS score", "0-100", "higher"),
]
ALERT_RT = {"LowBatt_AckRT_s": "Low battery", "Wind_AckRT_s": "Wind warning", "Status_AckRT_s": "Status check"}

KEY = ["ParticipantID", "Session", "Dashboard", "Trial"]


def load_csvs(pattern):
    """Concatenate every matching CSV under data/raw/, keeping the last copy of a re-run flight."""
    files = sorted(RAW.rglob(pattern))
    if not files:
        return pd.DataFrame(columns=KEY)
    df = pd.concat((pd.read_csv(f, dtype={"Date": str}) for f in files), ignore_index=True)
    df = df[df["Trial"].isin(TRIALS)]
    return df.drop_duplicates(subset=KEY, keep="last")


def load_heart_rate():
    """Heart-rate change from rest per participant per dashboard."""
    files = sorted(RAW.rglob("*_heart_rate.csv"))
    if not files:
        return pd.DataFrame(columns=["ParticipantID", "Dashboard", "HR_change_bpm"])
    hr = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    wide = hr.pivot_table(index="participant_id", columns="window", values="mean_hr_bpm")
    out = pd.DataFrame({d: wide[d] - wide["baseline"] for d in DASHBOARDS if d in wide and "baseline" in wide})
    out = out.rename_axis(columns="Dashboard").stack().rename("HR_change_bpm").reset_index()
    return out.rename(columns={"participant_id": "ParticipantID"})


def load_flights():
    """One row per Trial 1 / Trial 2 flight, with surveys and heart rate joined on."""
    flights = load_csvs("*_summary.csv")
    if flights.empty:
        return flights
    for col in flights.columns:
        if col.endswith(("_s", "_m", "_pct")) or col in ("GatesPassed", "MissedAlerts", "Collisions"):
            flights[col] = pd.to_numeric(flights[col], errors="coerce")  # e.g. "not_triggered" -> NaN
    # Same as the workbook: average of the A-press times for the alerts that appeared
    flights["MeanAlertRT_s"] = flights[list(ALERT_RT)].mean(axis=1)

    surveys = load_csvs("*_survey.csv")
    if not surveys.empty:
        flights = flights.merge(surveys[KEY + ["NASA_TLX_raw", "SUS_score"]], on=KEY, how="left")
    hr = load_heart_rate()
    if not hr.empty:
        flights = flights.merge(hr, on=["ParticipantID", "Dashboard"], how="left")
    return flights


def per_participant(flights, by, values):
    return flights.pivot_table(index="ParticipantID", columns=by, values=values, aggfunc="mean")


def paired_row(a, b, label, unit, better, names):
    """Paired t-test on two aligned Series; only participants with both values count."""
    pair = pd.concat([a, b], axis=1, keys=names).dropna()
    n = len(pair)
    diff = pair[names[0]] - pair[names[1]]
    row = {
        "Measure": label, "Unit": unit, "Better": better, "n (pairs)": n,
        f"{names[0]} mean": pair[names[0]].mean(), f"{names[0]} SD": pair[names[0]].std(),
        f"{names[1]} mean": pair[names[1]].mean(), f"{names[1]} SD": pair[names[1]].std(),
        "Mean diff": diff.mean(), "SD of diff": diff.std(),
        "t": np.nan, "df": n - 1 if n else np.nan, "p (two-tailed)": np.nan, "Effect size dz": np.nan,
    }
    if n >= 2 and diff.std() > 0:
        result = stats.ttest_rel(pair[names[0]], pair[names[1]])
        row["t"], row["p (two-tailed)"] = result.statistic, result.pvalue
        row["Effect size dz"] = diff.mean() / diff.std()
    row["Significant (p < .05)?"] = "yes" if row["p (two-tailed)"] < 0.05 else "no"
    return row


def paired_stats(flights):
    """The 5_Stats table: Nimbus minus AeroDash for each measure."""
    measures = [m for m in MEASURES if m[0] in flights.columns]
    wide = per_participant(flights, "Dashboard", [m[0] for m in measures])
    rows = [paired_row(wide[col].get(DASHBOARDS[0]), wide[col].get(DASHBOARDS[1]), label, unit, better, DASHBOARDS)
            for col, label, unit, better in measures
            if col in wide and all(d in wide[col] for d in DASHBOARDS)]
    return pd.DataFrame(rows)


def learning_effect(flights):
    """Trial 1 minus Trial 2, whichever dashboard it was: a consistent gap points to practice."""
    wide = per_participant(flights, "Trial", ["TaskTime_s", "MeanAlertRT_s"])
    rows = [paired_row(wide[col].get(TRIALS[0]), wide[col].get(TRIALS[1]), label, unit, better, TRIALS)
            for col, label, unit, better in MEASURES
            if col in ("TaskTime_s", "MeanAlertRT_s") and col in wide and all(t in wide[col] for t in TRIALS)]
    return pd.DataFrame(rows)


def group_means(flights):
    """Descriptive only: groups are too small for significance tests."""
    cols = ["MeanAlertRT_s", "GatesPassed", "Collisions", "MeanPathDeviation_m", "TaskTime_s"]
    return (flights.groupby(["Group", "Dashboard"])
            .agg(flights_n=("ParticipantID", "size"), **{c: (c, "mean") for c in cols})
            .reset_index())


def main():
    flights = load_flights()
    if flights.empty:
        print("No Trial 1 / Trial 2 summary CSVs found under data/raw/ yet.")
        return
    print(f"Loaded {len(flights)} flights from {flights['ParticipantID'].nunique()} participants.")
    for name, table in (("Paired t-tests (Nimbus minus AeroDash)", paired_stats(flights)),
                        ("Learning effect (Trial 1 minus Trial 2)", learning_effect(flights)),
                        ("Group means", group_means(flights))):
        print(f"\n== {name} ==\n{table.round(3).to_string(index=False)}")


if __name__ == "__main__":
    main()
