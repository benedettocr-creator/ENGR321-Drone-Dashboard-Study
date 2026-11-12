# ENGR 321 Project 2: Drone Delivery Dashboard Study

ENGR 321 (Human Factors Engineering) study comparing two drone delivery dashboards, **Nimbus Express** and **AeroDash**. Participants fly a simulated delivery route while the dashboard beside the flight view shows three alerts: low battery, wind warning, and a status check. We measure how fast they notice and act on each alert, how well they fly, their heart rate, and their workload (NASA-TLX) and usability (SUS) ratings.

**🚁 [Open the simulator live in Chrome →](https://jtmuir06-cpu.github.io/aerodash-app/drone-sim.html)** No download needed. Use a laptop or desktop. If the link doesn't load, download [`simulation/drone_sim.html`](simulation/drone_sim.html) and drag it into Chrome instead.

**📄 [Read the current report → report/REPORT.md](report/REPORT.md)**. It rebuilds itself from the data every time someone uploads.

> **This repository is public.** Only coded participant IDs (P001, P002, …) go here. Never commit names, consent forms, face or screen videos, or Apple Health exports. The upload tool and a pre-commit hook block these, but stay careful.

## How it works

```
Run a session      →  Upload with tools/ingest.py   →  git push  →  GitHub Actions checks the data
(drone_sim.html)      (checks and files the CSVs)                   and rebuilds report/REPORT.md
```

Each teammate (or their AI agent) uploads their own participants. Every participant has their own folder, so uploads never collide.

## Set up once

```bash
git clone https://github.com/benedettocr-creator/ENGR321-Drone-Dashboard-Study.git
```

```bash
cd ENGR321-Drone-Dashboard-Study && git config core.hooksPath .githooks
```

Uploading needs only Python 3. Previewing the report locally also needs `pip install -r requirements.txt`.

## Running a session

1. Open `simulation/drone_sim.html` in Google Chrome on a laptop or desktop (see [`READ_ME_FIRST.txt`](simulation/READ_ME_FIRST.txt)).
2. Follow the setup screen: enter the participant ID (**P001 format, never a name**), start the Apple Watch Workout, and connect the camera and screen.
3. Run **Baseline rest → Practice → Trial 1 → Trial 2**. The sim picks the dashboard and alert order from the participant ID ([`data/session_schedule.csv`](data/session_schedule.csv)).
4. The browser downloads CSVs and videos after each run. Move the videos to the group drive.

## Uploading data

**With an AI agent:** open the repo in Claude Code and say *"upload my session data from Downloads"*, or run `/upload-session-data`. The agent follows [`CLAUDE.md`](CLAUDE.md). Other agents read [`AGENTS.md`](AGENTS.md).

**By hand:**

```bash
python tools/ingest.py add ~/Downloads
```

```bash
python tools/ingest.py hr P003 --apple-health ~/Downloads/export.zip
```

```bash
python tools/ingest.py status
```

```bash
git add data/raw && git commit -m "Add P003 session data" && git pull --rebase && git push
```

`add` copies only valid simulator CSVs into `data/raw/<ParticipantID>/` and leaves out videos and health exports. `hr` works out mean heart rate for the baseline and both flights from the Apple Health export, using the sim's start and end times. You can also type the values in with `--baseline 72 --nimbus 88 --aerodash 95`. `status` lists what each participant is still missing.

## The report

- [`report/REPORT.md`](report/REPORT.md) is **generated**, in IEEE conference structure. Don't edit it.
- To change the text, edit [`report/template.md`](report/template.md); numbers, tables, and figures fill in from `{{placeholders}}`.
- Preview locally with `python tools/build_report.py`, which writes to `build/`.
- The stats are two-tailed paired t-tests (Nimbus minus AeroDash), the same as the `5_Stats` tab of [`analysis/Project2_Analysis_Workbook.xlsx`](analysis/Project2_Analysis_Workbook.xlsx). The sim's **Export results workbook** button still works as a cross-check.

## What's where

| Path | Contents |
| --- | --- |
| [`simulation/`](simulation/) | `drone_sim.html`, the simulator (one offline file) |
| [`data/raw/`](data/raw/) | One folder per participant: sim CSVs plus `<PID>_heart_rate.csv`. See [`data/README.md`](data/README.md) |
| [`analysis/`](analysis/) | Course workbook template and `analyze.py` |
| [`tools/`](tools/) | `ingest.py` (upload and checks) and `build_report.py` |
| [`report/`](report/) | `template.md` (edit this) and the generated `REPORT.md`, `figures/`, `results/` |
| [`CLAUDE.md`](CLAUDE.md), [`.claude/skills/`](.claude/skills/) | Instructions for teammates' AI agents |

Changes to `simulation/`, `analysis/`, or `tools/` should go through a pull request so someone checks them; GitHub Actions runs the same checks on pull requests.

## Related

- Nimbus Express dashboard: [benedettocr-creator/ENGR321-Drone-Delivery-Dashboard](https://github.com/benedettocr-creator/ENGR321-Drone-Delivery-Dashboard)
- AeroDash dashboard: [jtmuir06-cpu.github.io/aerodash-app](https://jtmuir06-cpu.github.io/aerodash-app/dashboard.html)
- The simulator includes [three.js](https://threejs.org/) r128 (MIT license).
