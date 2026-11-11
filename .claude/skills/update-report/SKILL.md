---
name: update-report
description: Preview, edit, or extend the study report (report/template.md, which builds report/REPORT.md). Use when the user wants to see current results, change report wording, fill a [TO COMPLETE] section, draft the discussion, add a table or figure, or asks why the report shows certain numbers.
---

# Update the report

`report/REPORT.md` is generated from `report/template.md` plus the data, by GitHub Actions on every push. Never edit `REPORT.md`, `report/figures/`, or `report/results/` directly.

1. `git pull --rebase origin main`, then `pip install -r requirements.txt` if needed.
2. Preview the current report: `python tools/build_report.py` writes `build/REPORT.md` and `build/figures/`. Read them before changing anything, so your edits match the current numbers.
3. Edit `report/template.md`:
   - Keep IEEE conference style: Roman-numeral `##` sections, lettered `###` subsections, `**TABLE N.** Title` above tables, `*Fig. N. Caption*` below figures, references numbered `[n]` in order of first citation.
   - Never type a number that comes from the data. Use a placeholder (`{{n_participants}}`, `{{table_paired}}`, …) or add one: compute it in `build()` in `tools/build_report.py`, add it to `values`, and use `{{name}}` in the template.
   - A new figure goes in `tools/build_report.py`. Follow the existing ones: Nimbus Express `#2a78d6`, AeroDash `#eb6834`, one thin gray line per participant for paired data, means with 95% CIs, hairline gridlines, no dual axes. Then look at the PNG before committing.
   - Discussion and Conclusion are interpretation. Base every claim on the generated results table, say when a difference is not significant, and keep the sample size in view. Leave the authors' own `[TO COMPLETE]` notes in place unless the user asks you to fill them.
4. Rebuild with `python tools/build_report.py` and check `build/REPORT.md` reads correctly: no leftover `{{…}}` and the figures render.
5. Commit only the template and any `tools/` or `analysis/` changes, then pull with rebase and push to `main`. GitHub Actions publishes the new `report/REPORT.md`.
