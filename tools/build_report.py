"""Build the report from report/template.md and the data in data/raw/.

    python tools/build_report.py              writes build/REPORT.md (a local preview, not committed)
    python tools/build_report.py --out report  what CI runs on main: writes report/REPORT.md

Output folder contents: REPORT.md, figures/*.png, results/*.csv (the full-precision tables).
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "analysis"), str(ROOT / "tools")]
import analyze  # noqa: E402
import ingest  # noqa: E402

TEMPLATE = ROOT / "report" / "template.md"

# Validated categorical slots 1 and 2 (light surface), plus recessive chart ink
COLOR = {"Nimbus": "#2a78d6", "AeroDash": "#eb6834"}
INK, INK_2, MUTED, GRID, AXIS, PAIR_LINE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#c3c2b7"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": AXIS, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": MUTED, "axes.titlesize": 9, "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white",
})


# ---------------------------------------------------------------- formatting

def fmt(v, digits=2):
    return "—" if pd.isna(v) else f"{v:.{digits}f}"


def p_text(p):
    return "p < .001" if p < 0.001 else f"p = {fmt_p(p)}"


def fmt_p(p):
    if pd.isna(p):
        return "—"
    return "< .001" if p < 0.001 else f"{p:.3f}".lstrip("0")


def md_table(df):
    return df.to_markdown(index=False) if not df.empty else "_No data yet._"


def paired_table(table, names, labels):
    """Report-style table: Measure | A M (SD) | B M (SD) | diff | t(df) | p | dz."""
    if table.empty:
        return "_No paired data yet._"
    a, b = names
    out = pd.DataFrame({
        "Measure": table["Measure"] + " (" + table["Unit"] + ", " + table["Better"] + " is better)",
        "n": table["n (pairs)"],
        labels[0]: [f"{fmt(m)} ({fmt(s)})" for m, s in zip(table[f"{a} mean"], table[f"{a} SD"])],
        labels[1]: [f"{fmt(m)} ({fmt(s)})" for m, s in zip(table[f"{b} mean"], table[f"{b} SD"])],
        "Diff": table["Mean diff"].map(fmt),
        "t(df)": [f"{fmt(t)} ({int(d)})" if not pd.isna(t) else "—" for t, d in zip(table["t"], table["df"])],
        "p": table["p (two-tailed)"].map(fmt_p),
        "d_z": table["Effect size dz"].map(fmt),
    })
    return out.to_markdown(index=False, disable_numparse=True)


def sentence(row):
    """One APA-style results sentence per measure."""
    name = row["Measure"]
    n, m, a = row["n (pairs)"], row["Nimbus mean"], row["AeroDash mean"]
    unit = "" if row["Unit"] in ("count", "0-100") else " " + row["Unit"]
    if pd.isna(row["t"]):
        return f"- **{name}:** not enough paired data for a test yet (n = {n})."
    stat = f"t({int(row['df'])}) = {row['t']:.2f}, {p_text(row['p (two-tailed)'])}, d_z = {row['Effect size dz']:.2f}"
    values = f"Nimbus Express {m:.2f}{unit} vs. AeroDash {a:.2f}{unit}"
    if row["p (two-tailed)"] < 0.05:
        lower = "Nimbus Express" if m < a else "AeroDash"
        better = lower if row["Better"] == "lower" else ("AeroDash" if lower == "Nimbus Express" else "Nimbus Express")
        return f"- **{name}** was significantly {'lower' if m < a else 'higher'} with Nimbus Express ({values}; {stat}), favoring **{better}**."
    return f"- **{name}** did not differ significantly ({values}; {stat})."


def headline(table):
    if table.empty:
        return "[Results will appear here once data is uploaded.]"
    sig = table[table["p (two-tailed)"] < 0.05]
    if sig.empty:
        return "No measure differed significantly between the dashboards at α = .05."
    parts = []
    for _, r in sig.iterrows():
        lower = "Nimbus Express" if r["Nimbus mean"] < r["AeroDash mean"] else "AeroDash"
        name = r["Measure"] if r["Measure"][:2].isupper() else r["Measure"][0].lower() + r["Measure"][1:]
        parts.append(f"{name} was lower with {lower} ({p_text(r['p (two-tailed)'])})")
    return "At α = .05, " + "; ".join(parts) + ". No other measure differed significantly."


GROUP_COLUMNS = {"flights_n": "Flights", "MeanAlertRT_s": "Alert RT (s)", "GatesPassed": "Gates passed",
                 "Collisions": "Collisions", "MeanPathDeviation_m": "Path deviation (m)", "TaskTime_s": "Task time (s)"}


# ---------------------------------------------------------------- figures

def ci95(x):
    x = pd.Series(x).dropna()
    if len(x) < 2:
        return np.nan
    return stats.t.ppf(0.975, len(x) - 1) * x.std() / np.sqrt(len(x))


def style_axis(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def figure_paired(flights, table, path):
    """Fig. 1: one thin line per participant between dashboards, colored mean with 95% CI."""
    panels = [m for m in analyze.MEASURES if m[0] in ("MeanAlertRT_s", "HR_change_bpm", "NASA_TLX_raw", "SUS_score")]
    wide = analyze.per_participant(flights, "Dashboard", [m[0] for m in panels if m[0] in flights])
    panels = [m for m in panels if m[0] in wide and all(d in wide[m[0]] for d in analyze.DASHBOARDS)]
    if not panels:
        return False
    fig, axes = plt.subplots(1, len(panels), figsize=(7.16, 2.9), squeeze=False)  # IEEE two-column width
    for ax, (col, label, unit, better) in zip(axes[0], panels):
        pair = wide[col][list(analyze.DASHBOARDS)].dropna()
        for _, r in pair.iterrows():
            ax.plot([0, 1], r.values, color=PAIR_LINE, linewidth=1, zorder=1)
        for i, d in enumerate(analyze.DASHBOARDS):
            ax.errorbar(i, pair[d].mean(), yerr=ci95(pair[d]), fmt="o", markersize=7, color=COLOR[d],
                        ecolor=COLOR[d], elinewidth=2, capsize=0, zorder=3,
                        markeredgecolor="white", markeredgewidth=1.5)
        stat = table.loc[table["Measure"] == label]
        p = stat["p (two-tailed)"].iloc[0] if len(stat) else np.nan
        ax.set_title(f"{label}\n{unit}, {better} is better\n" + ("" if pd.isna(p) else p_text(p)),
                     loc="left", fontsize=8, linespacing=1.3)
        ax.set_xticks([0, 1], [analyze.DASHBOARD_NAMES[d].replace(" ", "\n") for d in analyze.DASHBOARDS])
        for tick, d in zip(ax.get_xticklabels(), analyze.DASHBOARDS):
            tick.set_color(INK)
        ax.set_xlim(-0.4, 1.4)
        style_axis(ax)
    fig.tight_layout(w_pad=1.5)
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


def figure_alerts(flights, path):
    """Fig. 2: reaction time to each alert type by dashboard, mean with 95% CI."""
    cols = [c for c in analyze.ALERT_RT if c in flights]
    if not cols:
        return False
    fig, ax = plt.subplots(figsize=(3.5, 2.7))
    top = 0
    offsets = {"Nimbus": -0.12, "AeroDash": 0.12}
    for d in analyze.DASHBOARDS:
        sub = flights[flights["Dashboard"] == d]
        means = [sub[c].mean() for c in cols]
        errs = [ci95(sub[c]) for c in cols]
        x = np.arange(len(cols)) + offsets[d]
        top = max(top, np.nanmax(np.add(means, np.nan_to_num(errs))))
        ax.errorbar(x, means, yerr=errs, fmt="o", markersize=7, color=COLOR[d], ecolor=COLOR[d], elinewidth=2,
                    capsize=0, label=analyze.DASHBOARD_NAMES[d], markeredgecolor="white", markeredgewidth=1.5)
    ax.set_xticks(range(len(cols)), [analyze.ALERT_RT[c] for c in cols])
    ax.set_ylabel("Time to press A (s)")
    ax.set_ylim(0, top * 1.1)
    style_axis(ax)
    fig.legend(frameon=False, loc="upper left", ncol=2, fontsize=8, labelcolor=INK, handletextpad=0.3,
               bbox_to_anchor=(0.1, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return True


# ---------------------------------------------------------------- build

def commit_id():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"


def build(out):
    figures, results = out / "figures", out / "results"
    figures.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    flights = analyze.load_flights()
    have = not flights.empty

    paired = analyze.paired_stats(flights) if have else pd.DataFrame()
    learning = analyze.learning_effect(flights) if have else pd.DataFrame()
    groups = analyze.group_means(flights) if have else pd.DataFrame()
    for name, table in (("paired_stats", paired), ("learning_effect", learning), ("group_means", groups)):
        table.to_csv(results / f"{name}.csv", index=False)

    fig1 = have and figure_paired(flights, paired, figures / "fig1_paired.png")
    fig2 = have and figure_alerts(flights, figures / "fig2_alert_rt.png")
    completeness = pd.DataFrame(ingest.completeness()).replace({True: "yes", False: "no"})
    dates = pd.to_datetime(flights["Date"], format="%Y%m%d", errors="coerce").dropna() if have else pd.Series(dtype="datetime64[ns]")
    group_counts = (flights.drop_duplicates("ParticipantID")["Group"].value_counts() if have else pd.Series(dtype=int))

    values = {
        "n_participants": str(flights["ParticipantID"].nunique() if have else 0),
        "n_flights": str(len(flights)),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "commit": commit_id(),
        "date_range": ("no sessions yet" if not len(dates) else f"sessions on {dates.min():%b %d, %Y}"
                       if dates.min() == dates.max() else f"sessions {dates.min():%b %d} to {dates.max():%b %d, %Y}"),
        "group_counts": ", ".join(f"{n} {g}" for g, n in group_counts.items()) or "groups not recorded yet",
        "headline": headline(paired),
        "table_paired": paired_table(paired, analyze.DASHBOARDS, ["Nimbus Express", "AeroDash"]),
        "results_sentences": "\n".join(sentence(r) for _, r in paired.iterrows()) if not paired.empty else "",
        "table_learning": paired_table(learning, analyze.TRIALS, ["Trial 1", "Trial 2"]),
        "table_groups": md_table(groups.round(2).replace({"Dashboard": analyze.DASHBOARD_NAMES}).rename(columns=GROUP_COLUMNS)),
        "table_completeness": md_table(completeness),
        "figure_paired": ("![Fig. 1](figures/fig1_paired.png)\n\n*Fig. 1. Each gray line is one participant; colored points are means with 95% confidence intervals.*"
                          if fig1 else "_Fig. 1 appears once paired data is uploaded._"),
        "figure_alerts": ("![Fig. 2](figures/fig2_alert_rt.png)\n\n*Fig. 2. Time from alert onset to pressing A, by alert type. Points are means with 95% confidence intervals.*"
                          if fig2 else ""),
    }
    text = TEMPLATE.read_text()
    unknown = set(re.findall(r"{{(\w+)}}", text)) - set(values)
    if unknown:
        raise SystemExit(f"Unknown placeholder(s) in template.md: {', '.join(sorted(unknown))}")
    text = re.sub(r"{{(\w+)}}", lambda m: values[m.group(1)], text)
    (out / "REPORT.md").write_text(text)
    print(f"Wrote {(out / 'REPORT.md').relative_to(ROOT)} ({values['n_participants']} participants, {values['n_flights']} flights)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="build", help="output folder, relative to the repo root (default: build)")
    out = ROOT / parser.parse_args().out
    build(out)


if __name__ == "__main__":
    main()
