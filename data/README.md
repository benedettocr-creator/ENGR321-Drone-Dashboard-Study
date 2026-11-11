# Data

Coded IDs only (P001, P002, …). No names, consent forms, videos, or Apple Health exports. This repo is public.

Add files with `python tools/ingest.py` (see the main README), never by hand. `python tools/ingest.py check` validates everything here; GitHub Actions and the pre-commit hook run it too.

## `raw/<ParticipantID>/`

| File | One row per | What's in it |
| --- | --- | --- |
| `*_Baseline_*_events.csv` | event | Start and end of the 3-minute seated rest, used to find resting heart rate |
| `*_events.csv` | event | Every logged event with a timestamp: alert onsets, A presses, gates, collisions, sync flashes |
| `*_telemetry.csv` | 0.1 s | Position, altitude, speed, battery, stick inputs, active alerts |
| `*_summary.csv` | flight | The row the analysis uses: alert reaction times, gates, collisions, path deviation, task time |
| `*_survey.csv` | survey | NASA-TLX subscales (0–100) and raw score; SUS answers (1–5) and score (0–100) |
| `<PID>_heart_rate.csv` | window | Mean heart rate for `baseline`, `Nimbus`, and `AeroDash`, from `ingest.py hr` |

`Dashboard` is `Nimbus` or `AeroDash`. `Trial` is `Practice`, `Trial1`, or `Trial2`; practice runs are ignored in analysis. `Wind_Onset_s = not_triggered` means the participant never climbed above 31 m, so the wind alert never appeared.

Heart-rate windows run from `baseline_start` to `baseline_end`, and from `trial_start` to `trial_end`, in each events CSV (`iso_time`, UTC). The watch, phone, and simulator PC must all set their clocks automatically.

## `session_schedule.csv`

The counterbalancing plan. It matches what the simulator assigns automatically: odd IDs fly Nimbus first, and the alert order rotates every two participants. From P007 the pattern repeats.
