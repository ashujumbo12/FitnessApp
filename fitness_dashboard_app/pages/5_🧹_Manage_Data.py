import streamlit as st
import pandas as pd
from sqlmodel import select
from db import get_session
from models import User, DailyMetric, Week, Measurement, Wellbeing, Adherence

st.set_page_config(page_title="🧹 Manage Data", page_icon="🧹", layout="wide")
st.title("🧹 Manage Data")

def to_df(rows):
    return pd.DataFrame([getattr(r, "model_dump", getattr(r, "dict", lambda: r.__dict__))() for r in rows])

with get_session() as sess:
    user = sess.exec(select(User)).first()

tab1, tab2 = st.tabs(["Daily", "Weekly"])

# ---- DAILY ----
with tab1:
    with get_session() as sess:
        rows = sess.exec(select(DailyMetric).where(DailyMetric.user_id==user.id)).all()
    df = to_df(rows)
    if df.empty:
        st.info("No daily entries yet.")
    else:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        # Add a virtual "delete" checkbox column
        df.insert(0, "🗑️ delete", False)
        edited = st.data_editor(
            df.sort_values("date"),
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "id": st.column_config.NumberColumn(disabled=True),
                "user_id": st.column_config.NumberColumn(disabled=True),
                "week_id": st.column_config.NumberColumn(),
                "run_km": st.column_config.NumberColumn(disabled=True),
                "🗑️ delete": st.column_config.CheckboxColumn(),
            },
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save changes"):
                with get_session() as sess:
                    for _, r in edited.iterrows():
                        dm = sess.get(DailyMetric, int(r["id"]))
                        if not dm:
                            continue

                        dm.date = pd.to_datetime(r["date"]).date()
                        if pd.notna(r.get("week_id")):
                            dm.week_id = int(r["week_id"])

                        dm.weight_kg = float(r["weight_kg"]) if pd.notna(r.get("weight_kg")) else None
                        dm.steps = int(r["steps"]) if pd.notna(r.get("steps")) else None

                        # 🔁 keep KM derived from steps
                        if dm.steps is not None:
                            dm.run_km = (dm.steps * 8.0) / (1780.0 * 5.0)
                        else:
                            dm.run_km = None

                        sess.add(dm)
                    sess.commit()
                st.success("Daily changes saved.")
        with c2:
            if st.button("🗑️ Delete selected"):
                ids = edited.loc[edited["🗑️ delete"] == True, "id"].tolist()
                if not ids:
                    st.warning("Select at least one row.")
                else:
                    with get_session() as sess:
                        for i in ids:
                            dm = sess.get(DailyMetric, int(i))
                            if dm: sess.delete(dm)
                        sess.commit()
                    st.success(f"Deleted {len(ids)} row(s).")

# ---- WEEKLY ----
with tab2:
    with get_session() as sess:
        weeks = sess.exec(select(Week).where(Week.user_id==user.id)).all()
        meas  = sess.exec(select(Measurement).where(Measurement.user_id==user.id)).all()
        wb    = sess.exec(select(Wellbeing).where(Wellbeing.user_id==user.id)).all()
        adh   = sess.exec(select(Adherence).where(Adherence.user_id==user.id)).all()

    w = to_df(weeks).rename(columns={"id":"week_id"}) if weeks else pd.DataFrame(columns=["week_id","week_number","start_date"])
    m = to_df(meas) if meas else pd.DataFrame(columns=["week_id"])
    wbdf = to_df(wb) if wb else pd.DataFrame(columns=["week_id"])
    ad = to_df(adh) if adh else pd.DataFrame(columns=["week_id"])

    out = w[["week_id","week_number","start_date"]] if not w.empty else pd.DataFrame(columns=["week_id","week_number","start_date"])
    for frame in (m, wbdf, ad):
        if not frame.empty:
            frame = frame.drop(columns=[c for c in ["user_id","id"] if c in frame.columns])
            out = out.merge(frame, on="week_id", how="left")

    if out.empty:
        st.info("No weekly entries yet.")
    else:
        out["start_date"] = pd.to_datetime(out["start_date"]).dt.date
        out.insert(0, "🗑️ delete", False)
        edited = st.data_editor(
            out.sort_values("week_number"),
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "🗑️ delete": st.column_config.CheckboxColumn(),
                "week_id": st.column_config.NumberColumn(disabled=True),
            },
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save weekly changes"):
                with get_session() as sess:
                    for _, r in edited.iterrows():
                        wk = sess.get(Week, int(r["week_id"]))
                        if wk:
                            wk.start_date = pd.to_datetime(r["start_date"]).date()
                            sess.add(wk)
                        def upsert(model, fields):
                            row = sess.exec(select(model).where(model.user_id==user.id, model.week_id==int(r["week_id"]))).first()
                            if not row: row = model(user_id=user.id, week_id=int(r["week_id"]))
                            for f in fields:
                                if f in edited.columns:
                                    val = r.get(f)
                                    setattr(row, f, None if pd.isna(val) else (int(val) if f.endswith(("issues","score")) else float(val)))
                            sess.add(row)
                        upsert(Measurement, ["r_biceps_in","l_biceps_in","chest_in","r_thigh_in","l_thigh_in","waist_navel_in"])
                        upsert(Wellbeing, ["sleep_issues","hunger_issues","stress_issues"])
                        upsert(Adherence, ["diet_score","workout_score"])
                    sess.commit()
                st.success("Weekly changes saved.")
        with c2:
            if st.button("🗑️ Delete selected week rows (all weekly records)"):
                ids = edited.loc[edited["🗑️ delete"] == True, "week_id"].tolist()
                if not ids:
                    st.warning("Select at least one row.")
                else:
                    with get_session() as sess:
                        for wid in ids:
                            for model in (Measurement, Wellbeing, Adherence):
                                row = sess.exec(select(model).where(model.user_id==user.id, model.week_id==int(wid))).first()
                                if row: sess.delete(row)
                        sess.commit()
                    st.success(f"Deleted records for {len(ids)} week(s).")
