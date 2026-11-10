# Data

Coded IDs only (P001, P002, …). No names, consent forms, videos, or raw Apple Health exports. This repo is public.

## `raw/<ParticipantID>/`: files from the simulator

| File | One row per | What's in it |
| --- | --- | --- |
| `*_Baseline_*_events.csv` | event | Start and end of the 3-minute seated rest, used to find resting heart rate |
| `*_events.csv` | event | Every logged event with a timestamp: alert onsets, A presses, gates, collisions, sync flashes |
| `*_telemetry.csv` | 0.1 s | Position, altitude, speed, battery, stick inputs, active alerts |
| `*_summary.csv` | flight | The row the analysis uses: alert reaction times, gates, collisions, path deviation, task time |
| `*_survey.csv` | survey | NASA-TLX subscales (0–100) and raw score; SUS answers (1–5) and score (0–100) |

`Dashboard` is `Nimbus` or `AeroDash`. `Trial` is `Practice`, `Trial1`, or `Trial2`; practice runs are ignored in analysis. `Wind_Onset_s = not_triggered` means the participant never climbed above 31 m, so the wind alert never appeared.

## `heart_rate.csv`: typed in by hand

| Column | Meaning |
| --- | --- |
| `participant_id` | P001, P002, … |
| `baseline_hr_bpm` | Mean HR during the 3-minute baseline rest |
| `nimbus_hr_bpm` | Mean HR during the Nimbus Express flight |
| `aerodash_hr_bpm` | Mean HR during the AeroDash flight |
| `notes` | Watch problems, gaps, etc. |

Use the `sync_flash_start` and `sync_flash_end` rows (the `iso_time` column) in each events CSV to choose the window in the Health app.

## `session_schedule.csv`

The counterbalancing plan. It matches what the simulator assigns automatically: odd IDs fly Nimbus first, and the alert order rotates every two participants. From P007 the pattern repeats. Fill in `group`, `session_date`, and `notes` after each session.
