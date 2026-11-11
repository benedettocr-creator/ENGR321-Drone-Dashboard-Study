"""Add simulator files to data/raw/ and check that everything there is safe to publish.

    python tools/ingest.py add ~/Downloads              copy sim CSVs into data/raw/<ParticipantID>/
    python tools/ingest.py add ~/Downloads --dry-run    show what would happen, change nothing
    python tools/ingest.py hr P003 --baseline 72 --nimbus 88 --aerodash 95
    python tools/ingest.py hr P003 --apple-health ~/Downloads/export.zip
    python tools/ingest.py check                        validate data/ (CI and the pre-commit hook run this)
    python tools/ingest.py status                       which files each participant still needs

Standard library only, so it runs before anything is installed.
"""

import argparse
import csv
import filecmp
import io
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"

# Column layouts written by simulation/drone_sim.html. A file with any other header is refused.
HEADERS = {
    "events": ["participant_id", "session", "dashboard", "trial", "epoch_ms", "iso_time", "trial_time_s",
               "event", "detail", "x_m", "z_m", "alt_m", "battery_pct", "alert_area_px"],
    "telemetry": ["epoch_ms", "trial_time_s", "x_m", "z_m", "alt_m", "speed_ms", "heading_deg", "battery_pct",
                  "in_throttle", "in_yaw", "in_pitch", "in_roll", "phase", "active_alerts", "wind_active",
                  "dist_to_target_m", "current_gate"],
    "summary": ["ParticipantID", "Session", "Group", "Dashboard", "Trial", "Route", "EventOrder", "EndReason",
                "TaskTime_s", "Delivered_YN", "LowBatt_AckRT_s", "LowBatt_TimeToCharge_s", "Wind_AckRT_s",
                "Wind_TimeToDescend_s", "Status_AckRT_s", "Status_AnswerRT_s", "Status_Answer", "LowBatt_Onset_s",
                "Wind_Onset_s", "Status_Onset_s", "GatesTotal", "GatesPassed", "GatesMissed", "MissedAlerts",
                "Collisions", "MeanPathDeviation_m", "FinalBattery_pct", "Date", "ScreenVideo", "FaceVideo"],
    "survey": ["ParticipantID", "Session", "Group", "Dashboard", "Trial", "Date", "TLX_Mental", "TLX_Physical",
               "TLX_Temporal", "TLX_Performance", "TLX_Effort", "TLX_Frustration", "NASA_TLX_raw"]
              + [f"SUS_Q{i}" for i in range(1, 11)] + ["SUS_score"],
    "heart_rate": ["participant_id", "window", "mean_hr_bpm", "n_samples", "start_utc", "end_utc", "source"],
}
GROUPS = {"ENGR 321 classmate", "CS major / esports club", "Other major"}
HR_WINDOWS = ("baseline", "Nimbus", "AeroDash")

TRIAL_FILE = re.compile(r"^(?P<pid>P\d{3})_(?P<sess>S\d+)_(?P<dash>Nimbus|AeroDash)_(?P<trial>Practice|Trial1|Trial2)"
                        r"_(?P<date>\d{8})_(?P<kind>events|telemetry|summary|survey)\.csv$")
BASELINE_FILE = re.compile(r"^(?P<pid>P\d{3})_(?P<sess>S\d+)_Baseline_(?P<date>\d{8})_(?P<kind>events)\.csv$")
HR_FILE = re.compile(r"^(?P<pid>P\d{3})_(?P<kind>heart_rate)\.csv$")
# Anything shaped like a sim file name, whatever was typed as the participant ID
SIM_SHAPED = re.compile(r"^(?P<pid>.+?)_S\w*_(Nimbus|AeroDash|Baseline)_.*\.(csv|webm|mp4)$")
BROWSER_COPY = re.compile(r" \(\d+\)(?=\.\w+$)")  # "..._summary (1).csv" from downloading twice

VIDEO_EXT = {".webm", ".mp4", ".mov", ".mkv", ".avi"}
HEALTH_EXPORT = {"export.zip", "export.xml", "export_cda.xml"}
MAX_BYTES = 25 * 1024 * 1024
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")


def parse_name(name):
    """Return the name's fields (pid, kind, ...) for a valid data file name, else None."""
    for pattern in (TRIAL_FILE, BASELINE_FILE, HR_FILE):
        m = pattern.match(name)
        if m:
            return m.groupdict()
    return None


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def validate(path, meta):
    """Problems with one data file's contents; an empty list means it is fine to publish."""
    if path.stat().st_size > MAX_BYTES:
        return [f"larger than {MAX_BYTES // 2**20} MB"]
    try:
        rows = read_rows(path)
    except (UnicodeDecodeError, csv.Error) as e:
        return [f"not a readable CSV ({e})"]
    if not rows:
        return ["empty file"]
    kind = meta["kind"]
    header, body = rows[0], rows[1:]
    if header != HEADERS[kind]:
        return [f"columns don't match the simulator's {kind} layout"]
    problems = []
    col = {name: i for i, name in enumerate(header)}
    expect = {"ParticipantID": meta["pid"], "participant_id": meta["pid"]}
    if kind != "heart_rate":
        expect.update(Session=meta["sess"], session=meta["sess"])
    if "dash" in meta:
        expect.update(Dashboard=meta["dash"], dashboard=meta["dash"], Trial=meta["trial"], trial=meta["trial"])
    for n, row in enumerate(body, start=2):
        for name, want in expect.items():
            if name in col and col[name] < len(row) and row[col[name]] != want:
                problems.append(f"row {n}: {name} is '{row[col[name]]}', file name says '{want}'")
        if "Group" in col and col["Group"] < len(row) and row[col["Group"]] not in GROUPS:
            problems.append(f"row {n}: unexpected Group '{row[col['Group']]}'")
        for cell in row:
            if EMAIL.search(cell) or PHONE.search(cell):
                problems.append(f"row {n}: looks like an email address or phone number")
        if kind == "heart_rate":
            if row[col["window"]] not in HR_WINDOWS:
                problems.append(f"row {n}: window must be one of {', '.join(HR_WINDOWS)}")
            try:
                if not 30 <= float(row[col["mean_hr_bpm"]]) <= 220:
                    problems.append(f"row {n}: heart rate outside 30-220 bpm")
            except ValueError:
                problems.append(f"row {n}: mean_hr_bpm is not a number")
        if len(problems) > 5:
            return problems[:5] + ["..."]
    return problems


# ---------------------------------------------------------------- add

def candidates(paths):
    for p in map(Path, paths):
        p = p.expanduser()
        if p.is_dir():
            yield from sorted(x for x in p.rglob("*") if x.is_file())
        elif p.is_file():
            yield p
        else:
            print(f"Not found: {p}")


def cmd_add(args):
    added = same = 0
    refused, held_back = [], 0
    for src in candidates(args.paths):
        if RAW in src.resolve().parents:
            continue
        name = BROWSER_COPY.sub("", src.name)
        if src.suffix.lower() in VIDEO_EXT or name in HEALTH_EXPORT or src.parent.name == "apple_health_export":
            held_back += bool(SIM_SHAPED.match(name) or name in HEALTH_EXPORT)
            continue
        meta = parse_name(name)
        if meta is None:
            m = SIM_SHAPED.match(name)
            if m:
                refused.append(f"{src.name}: participant ID '{m['pid']}' is not a coded ID like P001")
            continue
        problems = validate(src, meta)
        if problems:
            refused.append(f"{src.name}: " + "; ".join(problems))
            continue
        dest = RAW / meta["pid"] / name
        if dest.exists():
            if filecmp.cmp(src, dest, shallow=False):
                same += 1
                continue
            if not args.replace:
                refused.append(f"{src.name}: a different {dest.name} is already uploaded (use --replace to overwrite)")
                continue
        print(("Would add " if args.dry_run else "Added ") + str(dest.relative_to(ROOT)))
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
        added += 1
    print(f"\n{added} file(s) {'to add' if args.dry_run else 'added'}, {same} already uploaded.")
    if held_back:
        print(f"{held_back} video / Apple Health file(s) left out on purpose: keep them on the group drive, never on GitHub.")
    if refused:
        print("\nREFUSED, fix and re-run:")
        for line in refused:
            print("  - " + line)
    return 1 if refused else 0


# ---------------------------------------------------------------- heart rate

def utc(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)


def flight_windows(pid):
    """(window, start, end) from the uploaded events CSVs, using the latest file of each kind."""
    windows = {}
    for f in sorted((RAW / pid).glob("*_events.csv")):
        meta = parse_name(f.name)
        rows = list(csv.DictReader(open(f, newline="", encoding="utf-8-sig")))
        if meta.get("trial") in ("Trial1", "Trial2"):
            window, start_ev, end_ev = meta["dash"], "trial_start", "trial_end"
        elif "dash" not in meta:
            window, start_ev, end_ev = "baseline", "baseline_start", "baseline_end"
        else:
            continue
        times = {r["event"]: r["iso_time"] for r in rows}
        if start_ev in times and end_ev in times:
            windows[window] = (utc(times[start_ev]), utc(times[end_ev]))
    return windows


def health_samples(path):
    """Yield (time, bpm) for every heart-rate record in an Apple Health export.zip or export.xml."""
    path = Path(path).expanduser()
    if path.suffix == ".zip":
        z = zipfile.ZipFile(path)
        member = next(n for n in z.namelist() if n.endswith("/export.xml") or n == "export.xml")
        stream = z.open(member)
    else:
        stream = open(path, "rb")
    with stream:
        for _, elem in ElementTree.iterparse(stream):
            if elem.tag == "Record" and elem.get("type") == "HKQuantityTypeIdentifierHeartRate":
                t = datetime.strptime(elem.get("startDate"), "%Y-%m-%d %H:%M:%S %z").astimezone(timezone.utc)
                yield t, float(elem.get("value"))
            elem.clear()


def cmd_hr(args):
    pid = args.pid
    if not re.fullmatch(r"P\d{3}", pid):
        print(f"'{pid}' is not a coded participant ID like P001.")
        return 1
    rows = []
    if args.apple_health:
        src = Path(args.apple_health).expanduser().resolve()
        if ROOT in src.parents:
            print("Warning: the Apple Health export is inside the repo. It is git-ignored, but move it out.")
        windows = flight_windows(pid)
        missing = [w for w in HR_WINDOWS if w not in windows]
        if missing:
            print(f"No start/end times for {', '.join(missing)} in data/raw/{pid}/. Upload the events CSVs first.")
            return 1
        found = {w: [] for w in windows}
        for t, bpm in health_samples(src):
            for w, (start, end) in windows.items():
                if start <= t <= end:
                    found[w].append(bpm)
        for w in HR_WINDOWS:
            start, end = windows[w]
            if not found[w]:
                print(f"No heart-rate samples between {start:%H:%M:%S} and {end:%H:%M:%S} UTC for {w}. "
                      "Was the Workout running, and are the watch and PC clocks set automatically?")
                return 1
            rows.append([pid, w, round(sum(found[w]) / len(found[w]), 1), len(found[w]),
                         start.isoformat(), end.isoformat(), "apple_health_export"])
    else:
        values = {"baseline": args.baseline, "Nimbus": args.nimbus, "AeroDash": args.aerodash}
        if None in values.values():
            print("Give --baseline, --nimbus and --aerodash, or --apple-health.")
            return 1
        rows = [[pid, w, values[w], "", "", "", "typed_in"] for w in HR_WINDOWS]
    dest = RAW / pid / f"{pid}_heart_rate.csv"
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows([HEADERS["heart_rate"]] + rows)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(buf.getvalue())
    problems = validate(dest, {"pid": pid, "kind": "heart_rate"})
    if problems:
        dest.unlink()
        print("Not saved: " + "; ".join(problems))
        return 1
    print(f"Saved {dest.relative_to(ROOT)}")
    for r in rows:
        print(f"  {r[1]:9} {r[2]} bpm" + (f"  ({r[3]} samples)" if r[3] else ""))
    return 0


# ---------------------------------------------------------------- check and status

ALLOWED_IN_DATA = {"README.md", "session_schedule.csv", "raw/.gitkeep"}


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files", "--cached"], cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []


def cmd_check(args):
    errors = []
    for rel in tracked_files():
        p = Path(rel)
        if p.suffix.lower() in VIDEO_EXT or p.name in HEALTH_EXPORT:
            errors.append(f"{rel}: videos and health exports must never be committed")
        if "consent" in p.name.lower():
            errors.append(f"{rel}: consent forms must never be committed")
    for f in sorted(DATA.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(DATA).as_posix()
        if rel in ALLOWED_IN_DATA:
            continue
        meta = parse_name(f.name)
        if meta is None or f.parent.parent != RAW or f.parent.name != meta["pid"]:
            errors.append(f"data/{rel}: not a recognized data file in the right folder")
            continue
        errors += [f"data/{rel}: {p}" for p in validate(f, meta)]
    if errors:
        print("Data check FAILED:")
        for e in errors:
            print("  - " + e)
        return 1
    n = sum(1 for p in RAW.iterdir() if p.is_dir())
    print(f"Data check passed ({n} participant folder(s)).")
    return 0


def completeness():
    """One row per participant: which files are present (used by status and the report)."""
    rows = []
    for folder in sorted(p for p in RAW.iterdir() if p.is_dir()):
        names = [parse_name(f.name) for f in folder.glob("*.csv")]
        names = [m for m in names if m]
        have = lambda **kw: any(all(m.get(k) == v for k, v in kw.items()) for m in names)
        row = {"Participant": folder.name,
               "Baseline": any("dash" not in m and m["kind"] == "events" for m in names)}
        for trial in ("Trial1", "Trial2"):
            dash = next((m["dash"] for m in names if m.get("trial") == trial), "")
            parts = [k for k in ("summary", "survey", "events", "telemetry") if have(trial=trial, kind=k)]
            row[trial] = f"{dash}: {len(parts)}/4" if dash else "missing"
        row["Heart rate"] = have(kind="heart_rate")
        row["Complete"] = row["Baseline"] and row["Heart rate"] and all(row[t].endswith("4/4") for t in ("Trial1", "Trial2"))
        rows.append(row)
    return rows


def cmd_status(args):
    rows = completeness()
    if not rows:
        print("No participant data uploaded yet.")
        return 0
    yn = lambda v: "yes" if v is True else ("no" if v is False else v)
    cols = list(rows[0])
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(yn(r[c]) for c in cols))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add", help="copy simulator CSVs into data/raw/")
    p.add_argument("paths", nargs="+", help="files or folders (e.g. ~/Downloads)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--replace", action="store_true", help="overwrite a different file with the same name")
    p.set_defaults(func=cmd_add)
    p = sub.add_parser("hr", help="save a participant's mean heart rates")
    p.add_argument("pid")
    p.add_argument("--baseline", type=float)
    p.add_argument("--nimbus", type=float)
    p.add_argument("--aerodash", type=float)
    p.add_argument("--apple-health", help="path to the Apple Health export.zip or export.xml")
    p.set_defaults(func=cmd_hr)
    sub.add_parser("check", help="validate everything under data/").set_defaults(func=cmd_check)
    sub.add_parser("status", help="list what each participant has").set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
