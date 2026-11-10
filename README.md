# ENGR 321 Project 2: Drone Delivery Dashboard Study

ENGR 321 (Human Factors Engineering) study comparing two drone delivery dashboards, **Nimbus Express** and **AeroDash**. Participants fly a simulated delivery route while the dashboard beside the flight view shows three alerts: low battery, wind warning, and a status check. We measure how fast they notice and act on each alert, how well they fly, their heart rate, and their workload (NASA-TLX) and usability (SUS) ratings.

- **Design:** within-subject. Every participant flies once with each dashboard, with order and alert order counterbalanced (see [`data/session_schedule.csv`](data/session_schedule.csv)).
- **Analysis:** two-tailed paired t-tests (α = 0.05), Nimbus minus AeroDash.

> **This repository is public.** Only coded participant IDs (P001, P002, …) go here. Never commit names, consent forms, face or screen videos, or raw Apple Health exports. `.gitignore` blocks the common ones, but check `git status` before every commit.

## What's where

| Folder | Contents |
| --- | --- |
| [`simulation/`](simulation/) | `drone_sim.html`, the simulator. One offline file: open it in Chrome. See [`READ_ME_FIRST.txt`](simulation/READ_ME_FIRST.txt). |
| [`data/raw/`](data/raw/) | The CSVs the simulator downloads, in one folder per participant (`data/raw/P001/`, …). |
| [`data/heart_rate.csv`](data/heart_rate.csv) | Mean heart rate for each time window, typed in from the Apple Watch. |
| [`data/session_schedule.csv`](data/session_schedule.csv) | Counterbalancing schedule plus session dates and notes. |
| [`analysis/`](analysis/) | `Project2_Analysis_Workbook.xlsx` (blank template) and `analyze.py` (the same stats, run from the CSVs). |
| [`results/`](results/) | Filled workbooks exported from the sim, plus `analyze.py` output. These tables go in the report. |

## Running a session

1. Open `simulation/drone_sim.html` in Google Chrome on a laptop or desktop.
2. Follow the setup screen: enter the participant ID, start the Apple Watch workout, and connect the camera and screen.
3. Run **Baseline rest → Practice → Trial 1 → Trial 2**. The sim picks the dashboard and alert order from the participant ID.
4. After each run, the browser downloads `_events.csv`, `_telemetry.csv`, `_summary.csv`, and (after a trial) `_survey.csv`, plus `_screen.webm` and `_face.webm` videos.
5. Move the **CSV files** into `data/raw/<ParticipantID>/`. Keep the **videos off GitHub** on the password-protected group drive.
6. From the Apple Watch data, type the participant's mean heart rate for the baseline, the Nimbus flight, and the AeroDash flight into `data/heart_rate.csv`. Use the SYNC times in the events CSV to pick each window.
7. Fill in the participant's row in `data/session_schedule.csv` (group, date, notes).

Data file names come from the sim: `ParticipantID_Session_Dashboard_Trial_YYYYMMDD_kind.csv`, for example `P001_S1_Nimbus_Trial1_20261112_summary.csv`. Don't rename them.

## Analyzing the data

**Workbook (main path):** on the sim's setup screen, click **Export results workbook**. Add the heart rates in the `3_HeartRate` tab, then save the file into `results/`. The `5_Stats` tab has the paired t-tests.

The sim stores results in that computer's browser. If sessions ran on several computers, use **Add CSV files from another computer…** to bring the summary and survey CSVs from `data/raw/` onto one machine before exporting.

**Python (cross-check):** `analyze.py` reads every CSV in `data/raw/` and computes the same 11 measures as `5_Stats`. It also runs a Trial 1 vs. Trial 2 learning-effect check and computes group means.

```bash
pip install -r requirements.txt
```

```bash
python analysis/analyze.py
```

Results are written to `results/` as `.csv` and `.md` tables; the Markdown tables paste straight into the report.

## Working together

1. Clone once: `git clone https://github.com/benedettocr-creator/ENGR321-Drone-Dashboard-Study.git`
2. Before you start: `git pull`
3. Add your files, check `git status` (no videos, names, or consent forms), then `git add`, `git commit -m "Add P003 session data"`, and `git push`.
4. For changes to `simulation/` or `analysis/`, use a branch and pull request so someone else checks it first. Data uploads can go straight to `main`.

New to git? [GitHub Desktop](https://desktop.github.com/) does all of this with buttons.

## Related

- Nimbus Express dashboard: [benedettocr-creator/ENGR321-Drone-Delivery-Dashboard](https://github.com/benedettocr-creator/ENGR321-Drone-Delivery-Dashboard)
- AeroDash dashboard: [jtmuir06-cpu.github.io/aerodash-app](https://jtmuir06-cpu.github.io/aerodash-app/dashboard.html)
- The simulator includes [three.js](https://threejs.org/) r128 (MIT license).
