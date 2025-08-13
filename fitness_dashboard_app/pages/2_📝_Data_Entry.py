import streamlit as st
import pandas as pd
from datetime import date, timedelta
from sqlmodel import select
from db import get_session
from models import User, Week, DailyMetric, Measurement, Wellbeing, Adherence

st.set_page_config(page_title="📝 Data Entry", page_icon="📝", layout="wide")
st.title("📝 Data Entry")

# ---------- helpers ----------
def steps_to_km(steps):
    s = pd.to_numeric(steps, errors="coerce")
    return float((s * 8.0) / (1780.0 * 5.0)) if pd.notna(s) else None

def monday_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

def get_or_create_week(sess, user_id: int, d: date) -> Week:
    start = monday_start(d)
    wk = sess.exec(
        select(Week).where(Week.user_id == user_id, Week.start_date == start)
    ).first()
    if wk:
        return wk
    # create new week with next number
    last = sess.exec(
        select(Week).where(Week.user_id == user_id).order_by(Week.week_number.desc())
    ).first()
    next_num = (last.week_number + 1) if last else 1
    wk = Week(user_id=user_id, week_number=next_num, start_date=start)
    sess.add(wk)
    sess.commit()
    sess.refresh(wk)
    return wk

# ---------- load user ----------
with get_session() as sess:
    user = sess.exec(select(User)).first()

tab1, tab2, tab3 = st.tabs(["Daily", "Weekly check-in", "Photos"])

# ==== DAILY ====
with tab1:
    st.subheader("Daily metrics")
    d = st.date_input("Date", value=date.today())
    weight = st.number_input("Weight (kg)", min_value=0.0, step=0.1, format="%.1f")
    steps  = st.number_input("Steps", min_value=0, step=100)
    # KM is hidden & derived
    km_val = steps_to_km(steps)

    if st.button("Save daily entry"):
        with get_session() as sess:
            wk = get_or_create_week(sess, user.id, d)
            wk_num = wk.week_number          # capture primitives BEFORE session closes
            wk_start = wk.start_date

            dm = DailyMetric(
                user_id=user.id,
                date=pd.to_datetime(d).date(),
                week_id=wk.id,
                weight_kg=(None if weight == 0 else weight),
                steps=int(steps) if steps else None,
                run_km=km_val
            )
            sess.add(dm)
            sess.commit()

        st.success(f"Saved daily entry for {d} (Week #{wk_num}, start {wk_start}).")

# ==== WEEKLY ====
with tab2:
    st.subheader("Weekly check-in (auto week from chosen date)")
    wd = st.date_input("Any date in the week", value=date.today())
    with get_session() as sess:
        wk = get_or_create_week(sess, user.id, wd)
    st.caption(f"Auto week: **Week {wk.week_number}**, starting **{wk.start_date} (Mon)**")

    c1, c2, c3 = st.columns(3)
    with c1:
        r_bi = st.number_input("Right biceps (in)", min_value=0.0, step=0.1)
        l_bi = st.number_input("Left biceps (in)",  min_value=0.0, step=0.1)
        chest = st.number_input("Chest (in)", min_value=0.0, step=0.1)
    with c2:
        r_th = st.number_input("Right thigh (in)", min_value=0.0, step=0.1)
        l_th = st.number_input("Left thigh (in)",  min_value=0.0, step=0.1)
        waist = st.number_input("Waist at navel (in)", min_value=0.0, step=0.1)
    with c3:
        sleep = st.slider("Sleep issues (0 best → 5 worst)", 0, 5, 0)
        hunger = st.slider("Hunger issues (0→5)", 0, 5, 0)
        stress = st.slider("Stress issues (0→5)", 0, 5, 0)
        diet = st.slider("Diet adherence (0→10)", 0, 10, 10)
        workout = st.slider("Workout adherence (0→10)", 0, 10, 10)

    if st.button("Save weekly check-in"):
        # Capture primitives so we don't touch a detached ORM object later
        wk_id = int(wk.id)
        wk_num = int(wk.week_number)

        with get_session() as sess:
            # Measurement (upsert)
            row = sess.exec(
                select(Measurement).where(
                    Measurement.user_id == user.id,
                    Measurement.week_id == wk_id
                )
            ).first()
            if not row:
                row = Measurement(user_id=user.id, week_id=wk_id)
            row.r_biceps_in = r_bi or None
            row.l_biceps_in = l_bi or None
            row.chest_in = chest or None
            row.r_thigh_in = r_th or None
            row.l_thigh_in = l_th or None
            row.waist_navel_in = waist or None
            sess.add(row)

            # Wellbeing (upsert)
            wb = sess.exec(
                select(Wellbeing).where(
                    Wellbeing.user_id == user.id,
                    Wellbeing.week_id == wk_id
                )
            ).first()
            if not wb:
                wb = Wellbeing(user_id=user.id, week_id=wk_id)
            wb.sleep_issues = int(sleep)
            wb.hunger_issues = int(hunger)
            wb.stress_issues = int(stress)
            sess.add(wb)

            # Adherence (upsert)
            ad = sess.exec(
                select(Adherence).where(
                    Adherence.user_id == user.id,
                    Adherence.week_id == wk_id
                )
            ).first()
            if not ad:
                # BUG in your snippet fixed here: use week_id=wk_id (not 'week_id == wk_id')
                ad = Adherence(user_id=user.id, week_id=wk_id)
            ad.diet_score = int(diet)
            ad.workout_score = int(workout)
            sess.add(ad)

            sess.commit()

        # Use the captured primitives (not the detached 'wk' object)
        st.success(f"Saved weekly check-in for Week {wk_num}.")

# ==== PHOTOS (placeholder) ====
with tab3:
    st.caption("Upload progress photos (optional).")
    st.info("This stub keeps your prior photo logic. If you want this page wired up, tell me and I’ll drop in the uploader with week auto-selection.")
