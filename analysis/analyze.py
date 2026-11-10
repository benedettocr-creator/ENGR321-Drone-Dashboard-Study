"""Paired t-tests comparing Nimbus Express and AeroDash, straight from the sim's CSVs.

This is a reproducible cross-check of the 5_Stats tab in
Project2_Analysis_Workbook.xlsx. It reads:

  data/raw/**/*_summary.csv   one row per flight, written by drone_sim.html
  data/raw/**/*_survey.csv    NASA-TLX and SUS answers after each flight
  data/heart_rate.csv         mean heart rate per window, typed in from the Apple Watch

and writes to results/:

  paired_stats.csv / .md      the same 11 measures as 5_Stats
  learning_effect.csv / .md   Trial 1 vs. Trial 2, whichever dashboard it was
  group_means.csv / .md       descriptive means by participant group (RQ3)

Run from the repository root:
    python analysis/analyze.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
HEART_RATE = ROOT / "data" / "heart_rate.csv"
RESULTS = ROOT / "results"

DASHBOARDS = ("Nimbus", "AeroDash")
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

KEY = ["ParticipantID", "Session", "Dashboard", "Trial"]


def load_csvs(pattern):
    """Concatenate every matching CSV under data/raw/, keeping the last copy of a re-run flight."""
    files = sorted(RAW.rglob(pattern))
    if not files:
        return pd.DataFrame(columns=KEY)
    df = pd.concat((pd.read_csv(f, dtype={"Date": str}) for f in files), ignore_index=True)
    df = df[df["Trial"].isin(TRIALS)]
    return df.drop_duplicates(subset=KEY, keep="last")


def load_flights():
    """One row per Trial 1 / Trial 2 flight, with surveys and heart rate joined on."""
    flights = load_csvs("*_summary.csv")
    for col in flights.columns:
        if col.endswith(("_s", "_m", "_pct")) or col in ("GatesPassed", "MissedAlerts", "Collisions"):
            flights[col] = pd.to_numeric(flights[col], errors="coerce")  # e.g. "not_triggered" -> NaN
    # Same as the workbook: average of the A-press times for the alerts that appeared
    flights["MeanAlertRT_s"] = flights[["LowBatt_AckRT_s", "Wind_AckRT_s", "Status_AckRT_s"]].mean(axis=1)

    surveys = load_csvs("*_survey.csv")
    if not surveys.empty:
        flights = flights.merge(surveys[KEY + ["NASA_TLX_raw", "SUS_score"]], on=KEY, how="left")

    if HEART_RATE.exists():
        hr = pd.read_csv(HEART_RATE).dropna(subset=["baseline_hr_bpm"])
        hr = hr.melt(id_vars=["participant_id", "baseline_hr_bpm"],
                     value_vars=["nimbus_hr_bpm", "aerodash_hr_bpm"],
                     var_name="Dashboard", value_name="flight_hr_bpm")
        hr["Dashboard"] = hr["Dashboard"].map({"nimbus_hr_bpm": "Nimbus", "aerodash_hr_bpm": "AeroDash"})
        hr["HR_change_bpm"] = hr["flight_hr_bpm"] - hr["baseline_hr_bpm"]
        hr = hr.rename(columns={"participant_id": "ParticipantID"})
        flights = flights.merge(hr[["ParticipantID", "Dashboard", "HR_change_bpm"]],
                                on=["ParticipantID", "Dashboard"], how="left")
    return flights


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


def save(table, name):
    table = table.round(3)
    table.to_csv(RESULTS / f"{name}.csv", index=False)
    (RESULTS / f"{name}.md").write_text(table.to_markdown(index=False) + "\n")
    print(f"\n== {name} ==\n{table.to_string(index=False)}")


def main():
    RESULTS.mkdir(exist_ok=True)
    flights = load_flights()
    if flights.empty:
        print("No Trial 1 / Trial 2 summary CSVs found under data/raw/ yet.")
        return
    print(f"Loaded {len(flights)} flights from {flights['ParticipantID'].nunique()} participants.")

    measures = [m for m in MEASURES if m[0] in flights.columns]

    # Nimbus minus AeroDash, as in the workbook
    by_dash = flights.pivot_table(index="ParticipantID", columns="Dashboard",
                                  values=[m[0] for m in measures], aggfunc="mean")
    rows = [paired_row(by_dash[col].get(DASHBOARDS[0]), by_dash[col].get(DASHBOARDS[1]),
                       label, unit, better, DASHBOARDS)
            for col, label, unit, better in measures
            if all(d in by_dash[col] for d in DASHBOARDS)]
    save(pd.DataFrame(rows), "paired_stats")

    # Trial 1 minus Trial 2: a consistent gap here points to a practice effect
    by_trial = flights.pivot_table(index="ParticipantID", columns="Trial",
                                   values=["TaskTime_s", "MeanAlertRT_s"], aggfunc="mean")
    rows = [paired_row(by_trial[col].get(TRIALS[0]), by_trial[col].get(TRIALS[1]), label, unit, better, TRIALS)
            for col, label, unit, better in MEASURES
            if col in ("TaskTime_s", "MeanAlertRT_s") and all(t in by_trial[col] for t in TRIALS)]
    if rows:
        save(pd.DataFrame(rows), "learning_effect")

    # Descriptive only: groups are too small for significance tests
    group_cols = ["MeanAlertRT_s", "GatesPassed", "Collisions", "MeanPathDeviation_m", "TaskTime_s"]
    groups = (flights.groupby(["Group", "Dashboard"])
              .agg(flights_n=("ParticipantID", "size"), **{c: (c, "mean") for c in group_cols})
              .reset_index())
    save(groups, "group_means")


if __name__ == "__main__":
    main()
