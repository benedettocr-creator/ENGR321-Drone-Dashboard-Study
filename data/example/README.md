# Example session (not study data)

A complete test run of the simulator, kept so teammates can see what an upload looks like. **It is never analyzed**: `analysis/analyze.py` and the report read only `data/raw/`.

- `P001/` is a practice session run on 2026-11-17 before real data collection. It does not belong to participant P001 in `data/raw/`.
- Its summary and survey CSVs were rebuilt from the simulator's exported results workbook, and its heart rate was typed in, so it has no trial events or telemetry files.

Add more test sessions here with `python tools/ingest.py add <folder> --example`.
