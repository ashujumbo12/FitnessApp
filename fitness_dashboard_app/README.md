# Fitness Progress — Local Dashboard (Streamlit + SQLite)

A local-first app to record daily/weekly fitness data and visualize progress with rich, filterable dashboards.
- Polished UI (Tailwind-ish CSS), keyboard-friendly forms, and photo gallery.
- Data stored in `data/fitness.db` (SQLite) + `data/photos/` for images.
- Import your existing Google Sheet (Progress Sheet) via CSV.

## Quickstart
1. Create a virtual env (recommended).
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   streamlit run app.py
   ```
4. The app runs locally on http://localhost:8501

## Pages
- **Dashboard**: KPIs and charts with powerful filters (date/week range, metrics, smoothing).
- **Data Entry**: Daily (weight, steps) and Weekly (measurements, wellbeing, adherence) + photo uploads.
- **Import/Export**: Import from CSV (template in `templates/progress_template.csv`). Export data and DB backups.
- **Settings**: Profile (height, goal weight, units).

## CSV Import (Progress Sheet format)
Export your Google Sheet “PROGRESS SHEET” as CSV and upload. Or use the template to understand columns.
- Daily: `date,weight_kg,steps`
- Weekly: `week_number,start_date,r_biceps_in,l_biceps_in,chest_in,r_thigh_in,l_thigh_in,waist_navel_in,sleep_issues,hunger_issues,stress_issues,diet_score,workout_score`

> Tip: If your sheet tracks Day1..Day7 per week, provide the start_date for Week N in the weekly row. The importer will infer dates for D1..D7 and map weights/steps accordingly.

## Backup/Restore
- Export CSVs for each table and a `.sqlite` file snapshot.

## Stack
- Streamlit (UI), Plotly (charts)
- SQLite + SQLModel/SQLAlchemy (storage)
