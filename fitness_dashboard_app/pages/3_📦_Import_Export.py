import streamlit as st
st.set_page_config(page_title="📥 Import / Export", page_icon="📥", layout="wide")

try:
    from google_progress_import import import_progress_sheet
except Exception:
    import_progress_sheet = None  # Google Sheets importer not available

import pandas as pd
from datetime import date, timedelta
from dateutil.parser import parse as parse_date
from sqlmodel import select
from sqlalchemy import delete as sqla_delete
from db import get_session
from models import User, DailyMetric, Week, Measurement, Wellbeing, Adherence
import io, os, shutil, sqlite3
from utils import load_css


# optional CSS (safe after set_page_config)
try:
    load_css()
except Exception:
    pass

st.title("📦 Import / Export")

st.subheader("Import from CSV (Progress Sheet format)")
tmpl = pd.DataFrame({
    "week_number":[1],
    "start_date":["2025-01-06"],
    "date":["2025-01-06"],
    "weight_kg":[88.9],
    "steps":[12319],
    "r_biceps_in":[12.5],
    "l_biceps_in":[12.3],
    "chest_in":[40.0],
    "r_thigh_in":[22.0],
    "l_thigh_in":[21.8],
    "waist_navel_in":[36.5],
    "sleep_issues":[1],
    "hunger_issues":[2],
    "stress_issues":[1],
    "diet_score":[9],
    "workout_score":[8],
})
st.download_button("Download CSV Template", data=tmpl.to_csv(index=False), file_name="progress_template.csv")

uploaded = st.file_uploader("Upload CSV", type=["csv"])
if uploaded and st.button("Import"):
    df = pd.read_csv(uploaded)
    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]
    required = ["date","weight_kg","steps","week_number","start_date"]
    if not set(required).issubset(set(df.columns)):
        st.error(f"Missing columns. Required: {required}")
    else:
        n_daily, n_week = 0, 0
        with get_session() as sess:
            user = sess.exec(select(User)).first()
            # Create or upsert weeks
            for _, row in df.iterrows():
                start = parse_date(str(row["start_date"])).date()
                wk = sess.exec(select(Week).where(Week.user_id==user.id, Week.start_date==start)).first()
                if not wk:
                    wk = Week(user_id=user.id, week_number=int(row["week_number"]), start_date=start)
                    sess.add(wk); sess.commit(); sess.refresh(wk); n_week += 1
                # daily
                d = parse_date(str(row["date"])).date()
                dm = sess.exec(select(DailyMetric).where(DailyMetric.user_id==user.id, DailyMetric.date==d)).first()
                if not dm: dm = DailyMetric(user_id=user.id, date=d, week_id=wk.id)
                dm.weight_kg = float(row["weight_kg"]) if not pd.isna(row["weight_kg"]) else None
                dm.steps = int(row["steps"]) if not pd.isna(row["steps"]) else None
                # keep KM derived from steps
                dm.run_km = ((dm.steps * 8.0) / (1780.0 * 5.0)) if dm.steps is not None else None
                dm.week_id = wk.id
                sess.add(dm); sess.commit(); n_daily += 1
                # Optional weekly rows if present
                def assign_weekly(model_cls, fields):
                    existing = sess.exec(select(model_cls).where(model_cls.user_id==user.id, model_cls.week_id==wk.id)).first()
                    if not existing:
                        existing = model_cls(user_id=user.id, week_id=wk.id)
                    changed = False
                    for f in fields:
                        if f in df.columns and f in row and not pd.isna(row[f]):
                            setattr(existing, f, float(row[f]) if "score" not in f and "issues" not in f else int(row[f]))
                            changed = True
                    if changed:
                        sess.add(existing); sess.commit()
                assign_weekly(Measurement, ["r_biceps_in","l_biceps_in","chest_in","r_thigh_in","l_thigh_in","waist_navel_in"])
                assign_weekly(Wellbeing, ["sleep_issues","hunger_issues","stress_issues"])
                assign_weekly(Adherence, ["diet_score","workout_score"])
        st.success(f"Imported {n_daily} daily rows; created {n_week} weeks.")

# helper: make export compatible with both SQLModel/Pydantic v1 & v2
def _row_to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    # fallback: use __dict__ without private attrs
    return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}

st.subheader("Export / Backup")
col1, col2 = st.columns(2)
with col1:
    if st.button("Export all tables to CSV"):
        from models import DailyMetric, Week, Measurement, Wellbeing, Adherence
        with get_session() as sess:
            import tempfile, zipfile
            tables = {
                "daily_metrics.csv": pd.DataFrame([_row_to_dict(r) for r in sess.exec(select(DailyMetric)).all()]),
                "weeks.csv": pd.DataFrame([_row_to_dict(r) for r in sess.exec(select(Week)).all()]),
                "measurements.csv": pd.DataFrame([_row_to_dict(r) for r in sess.exec(select(Measurement)).all()]),
                "wellbeing.csv": pd.DataFrame([_row_to_dict(r) for r in sess.exec(select(Wellbeing)).all()]),
                "adherence.csv": pd.DataFrame([_row_to_dict(r) for r in sess.exec(select(Adherence)).all()]),
            }
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for name, df in tables.items():
                    z.writestr(name, df.to_csv(index=False))
            st.download_button("Download CSV bundle", data=zbuf.getvalue(), file_name="fitness_export.zip")
with col2:
    if st.button("Backup SQLite DB"):
        path = os.path.join("data","fitness.db")
        if os.path.exists(path):
            with open(path,"rb") as f:
                st.download_button("Download DB", data=f.read(), file_name="fitness.db")
        else:
            st.warning("No DB found yet.")
 


st.subheader("🧹 Remove imported data (safe cleanup)")

with st.expander("Delete data by date range or week numbers", expanded=False):
    mode = st.radio("Choose cleanup mode", ["By date range", "By week numbers"], horizontal=True)

    if mode == "By date range":
        colA, colB = st.columns(2)
        with colA:
            d_from = st.date_input("From date", value=date.today() - timedelta(days=30))
        with colB:
            d_to = st.date_input("To date", value=date.today())

        also_delete_weekly = st.checkbox("Also remove weekly check-ins (Measurement/Wellbeing/Adherence) for weeks fully removed", value=True)
        delete_empty_weeks = st.checkbox("Delete Week rows that become empty", value=True)

        # Preview counts
        if st.button("Preview impact", key="preview_by_date"):
            with get_session() as sess:
                # Daily rows in range
                q_daily = sess.exec(
                    select(DailyMetric).where(DailyMetric.date >= d_from, DailyMetric.date <= d_to)
                ).all()
                st.info(f"Daily rows to delete: {len(q_daily)}")

                # Weeks touched
                touched_week_ids = sorted({dm.week_id for dm in q_daily if dm.week_id is not None})
                st.write(f"Weeks touched: {touched_week_ids if touched_week_ids else 'None'}")

                if also_delete_weekly and touched_week_ids:
                    # Which of those weeks would become empty (no dailies left after deletion)
                    empty_weeks = []
                    for wid in touched_week_ids:
                        # remaining dailies outside the range
                        remaining = sess.exec(
                            select(DailyMetric).where(
                                DailyMetric.week_id == wid,
                                (DailyMetric.date < d_from) | (DailyMetric.date > d_to)
                            )
                        ).all()
                        if len(remaining) == 0:
                            empty_weeks.append(wid)
                    st.write(f"Weeks that would be fully removed (and thus weekly check-ins eligible for deletion): {empty_weeks if empty_weeks else 'None'}")

        confirm = st.text_input("Type DELETE to confirm", "")
        if st.button("Delete now", key="delete_by_date"):
            if confirm != "DELETE":
                st.error("Please type DELETE to confirm.")
            else:
                with get_session() as sess:
                    # Collect affected weeks before deletion
                    q_daily = sess.exec(
                        select(DailyMetric).where(DailyMetric.date >= d_from, DailyMetric.date <= d_to)
                    ).all()
                    touched_week_ids = sorted({dm.week_id for dm in q_daily if dm.week_id is not None})

                    # Delete daily metrics in range
                    sess.exec(
                        sqla_delete(DailyMetric).where(DailyMetric.date >= d_from, DailyMetric.date <= d_to)
                    )
                    sess.commit()

                    if also_delete_weekly and touched_week_ids:
                        # Determine weeks that became empty
                        empty_weeks = []
                        for wid in touched_week_ids:
                            remaining = sess.exec(select(DailyMetric).where(DailyMetric.week_id == wid)).all()
                            if len(remaining) == 0:
                                empty_weeks.append(wid)

                        if empty_weeks:
                            # Remove weekly one-to-ones for empty weeks
                            sess.exec(sqla_delete(Measurement).where(Measurement.week_id.in_(empty_weeks)))
                            sess.exec(sqla_delete(Wellbeing).where(Wellbeing.week_id.in_(empty_weeks)))
                            sess.exec(sqla_delete(Adherence).where(Adherence.week_id.in_(empty_weeks)))
                            sess.commit()

                            if delete_empty_weeks:
                                sess.exec(sqla_delete(Week).where(Week.id.in_(empty_weeks)))
                                sess.commit()

                st.success("Deletion completed. Check the dashboard.")

    else:
        # By week numbers
        col1, col2 = st.columns(2)
        with col1:
            wk_from = st.number_input("From week number", min_value=1, value=1, step=1)
        with col2:
            wk_to = st.number_input("To week number", min_value=1, value=1, step=1)

        also_delete_weekly2 = st.checkbox("Also remove weekly check-ins (Measurement/Wellbeing/Adherence) for these weeks", value=True, key="wk_weekly")
        delete_weeks2 = st.checkbox("Delete the Week rows themselves", value=True, key="wk_weeks")

        if st.button("Preview impact", key="preview_by_week"):
            with get_session() as sess:
                week_rows = sess.exec(
                    select(Week).where(Week.week_number >= wk_from, Week.week_number <= wk_to)
                ).all()
                wids = [w.id for w in week_rows]
                st.info(f"Weeks found: {len(week_rows)} ({wids})")

                daily_count = 0
                if wids:
                    daily_count = len(sess.exec(select(DailyMetric).where(DailyMetric.week_id.in_(wids))).all())
                st.write(f"Daily rows to delete: {daily_count}")

        confirm2 = st.text_input("Type DELETE to confirm", "", key="confirm_week")
        if st.button("Delete now", key="delete_by_week"):
            if confirm2 != "DELETE":
                st.error("Please type DELETE to confirm.")
            else:
                with get_session() as sess:
                    week_rows = sess.exec(
                        select(Week).where(Week.week_number >= wk_from, Week.week_number <= wk_to)
                    ).all()
                    wids = [w.id for w in week_rows]

                    if wids:
                        # Delete dailies
                        sess.exec(sqla_delete(DailyMetric).where(DailyMetric.week_id.in_(wids)))
                        sess.commit()

                        if also_delete_weekly2:
                            sess.exec(sqla_delete(Measurement).where(Measurement.week_id.in_(wids)))
                            sess.exec(sqla_delete(Wellbeing).where(Wellbeing.week_id.in_(wids)))
                            sess.exec(sqla_delete(Adherence).where(Adherence.week_id.in_(wids)))
                            sess.commit()

                        if delete_weeks2:
                            sess.exec(sqla_delete(Week).where(Week.id.in_(wids)))
                            sess.commit()

                st.success("Deletion completed for selected weeks.")

if import_progress_sheet:
    st.subheader("Import from original PROGRESS SHEET (as-is)")

    DEFAULT_ID = "1DI_3qReYN05ouvBx6bv161UKk233GrYh2vLi5H-tOVI"

    with st.form("import_progress_sheet"):
        sid = st.text_input("Spreadsheet ID", value=DEFAULT_ID)

        # Try to populate worksheet options dynamically
        import gspread
        ws_options = []
        try:
            if "gcp_service_account" in st.secrets and sid:
                gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
                sh = gc.open_by_key(sid)
                ws_options = [ws.title for ws in sh.worksheets()]  # should list "Check-in"
        except Exception:
            pass

        ws_title = st.selectbox(
            "Worksheet (tab) to import",
            options=ws_options or ["Check-in"],   # default to Check-in if list fails
            index=(ws_options.index("Check-in") if "Check-in" in ws_options else 0)
        )

        submitted = st.form_submit_button("🔄 Import now")

    if submitted:
        try:
            res = import_progress_sheet(sid, ws_title)
            st.success(f"Imported: {res['daily_upserts']} daily rows, {res['weekly_upserts']} weekly rows.")
            st.toast("Sync complete — head to the Dashboard!", icon="✅")
        except Exception as e:
            st.error("Import failed. Check that the service account has access and the sheet structure matches.")
            st.exception(e)

    st.markdown("---")
    st.caption(
        "Tip: The importer reads the labeled blocks (Day 1…7, Daily Walking Data, "
        "Measurements, Wellbeing, Adherence) and weeks from the 'Week 1…' header row. "
        "If your sheet uses slightly different labels, tell me and I’ll add aliases."
    )
else:
    st.subheader("Import from Google Sheets")
    st.info(
        "Google Sheets importer is currently disabled or not installed. "
        "The rest of this page (CSV import/export/cleanup) still works.\n\n"
        "To enable the Sheets importer:\n"
        "1) Keep `google_progress_import.py` in the project root\n"
        "2) Install deps: `pip install gspread gspread-dataframe google-auth`\n"
        "3) Add your service account to `.streamlit/secrets.toml` and share the sheet with it."
    )