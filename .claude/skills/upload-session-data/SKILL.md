---
name: upload-session-data
description: Upload a participant's drone simulator files (summary, survey, events, telemetry CSVs, and heart rate) from the user's computer to this repo. Use when the user ran a study session and wants their data on GitHub, mentions the sim downloads, a participant ID like P003, or their Apple Watch heart-rate data.
---

# Upload session data

This repo is public. Follow CLAUDE.md's privacy rule throughout: coded IDs only; no videos, Apple Health exports, names, or consent forms.

1. Make sure the hook is on and the clone is current:
   ```bash
   git config core.hooksPath .githooks && git pull --rebase origin main
   ```
2. Ask the user where the simulator files are if they haven't said (usually their Downloads folder), and which participant IDs they ran.
3. Preview, show the user the output, then add:
   ```bash
   python tools/ingest.py add <folder> --dry-run
   python tools/ingest.py add <folder>
   ```
   If anything is REFUSED, tell the user which file and why, and stop for that file. A participant ID that isn't `P` plus three digits means the ID was typed wrong in the sim, and it may be a person's name: don't rename or edit the file to get it through. A different file with the same name already uploaded is a re-run: ask the user before using `--replace`.
4. Heart rate for each participant uploaded:
   - If the user has the Apple Health export: `python tools/ingest.py hr <PID> --apple-health <path>`. If it reports no samples in a window, the watch Workout wasn't running or a clock was off: tell the user and don't guess values.
   - Otherwise ask the user for the three means (baseline, Nimbus, AeroDash) and run `python tools/ingest.py hr <PID> --baseline <bpm> --nimbus <bpm> --aerodash <bpm>`.
5. Run `python tools/ingest.py check` (it must pass) and `python tools/ingest.py status`. Tell the user what each participant is still missing.
6. Commit only the new data folders, then push:
   ```bash
   git add data/raw/<PID> ...
   git commit -m "Add <PIDs> session data"
   git pull --rebase origin main && git push origin main
   ```
7. Tell the user the push will rebuild `report/REPORT.md` automatically in about two minutes. The status of the run is on the repo's Actions tab.
