# pages/1_📊_Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlmodel import select
from db import get_session
from models import User
from utils import load_daily_df, load_weekly_df, rolling_avg, load_expenses_df, expense_metrics, load_css

st.set_page_config(page_title="📊 Progress Dashboard", page_icon="📊", layout="wide")
load_css(show_warning=False)

st.title("📊 Fitness Dashboard")

# ---------- helpers ----------
def steps_to_km(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return (s * 8.0) / (1780.0 * 5.0)

def issue_emoji(v):
    try: v = int(v)
    except Exception: return "—"
    return ["😄","🙂","😐","😕","😣","😫"][max(0, min(5, v))]

def adherence_emoji(v):
    try: v = int(v)
    except Exception: return "—"
    if v >= 8: return "🔥"
    if v >= 6: return "👍"
    if v >= 4: return "⚠️"
    return "❌"

def nice_y_range(series: pd.Series, pad_ratio=0.10):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty: return None
    lo, hi = float(s.min()), float(s.max())
    if hi == lo:
        delta = max(abs(hi) * pad_ratio, 0.5)
        return [lo - delta, hi + delta]
    pad = (hi - lo) * pad_ratio
    return [lo - pad, hi + pad]

# ---------- load ----------
with get_session() as sess:
    user = sess.exec(select(User)).first()
    daily_raw = load_daily_df(sess, user.id)
    weekly = load_weekly_df(sess, user.id)
    expenses_df = load_expenses_df(sess, user.id)

if daily_raw.empty:
    st.info("No data yet. Add entries in **📝 Data Entry**.")
    st.stop()

# ---------- sidebar ----------
with st.sidebar:
    st.header("Filters")
    min_d = pd.to_datetime(daily_raw["date"]).dt.date.min()
    max_d = pd.to_datetime(daily_raw["date"]).dt.date.max()
    # Date range selector (robust to single-date selections)
    dr = st.date_input("Date range", value=(min_d, max_d))
    if isinstance(dr, tuple) and len(dr) == 2:
        date_start, date_end = dr
    else:
        # If user selects a single date or Streamlit returns non-tuple, coerce to (d, d)
        try:
            date_start = pd.to_datetime(dr).date()
            date_end = date_start
        except Exception:
            date_start, date_end = (min_d, max_d)
    show_weight = st.checkbox("Show weight trend", True)
    show_steps  = st.checkbox("Show steps", True)
    show_km     = st.checkbox("Show derived KM", True)
    smooth      = st.slider("Weight smoothing (days)", 1, 14, 7)
    show_weekly_loss = st.checkbox("Show weekly weight change", True)
    step_goal   = st.number_input("Steps goal", 10000, step=500, value=10000)
    adherence_min = st.slider("Min adherence (diet & workout)", 0, 10, 0)
    show_tables = st.checkbox("Show Daily & Weekly tables", True)

# ---------- DAILY: canonical day + resample to 1 row/day ----------
daily = daily_raw.copy()

# canonicalize timestamps: make tz-aware in UTC, then convert to naive midnight
ts = pd.to_datetime(daily["date"], utc=True, errors="coerce")
daily["day"] = pd.to_datetime(ts.dt.date)  # naive midnight (YYYY-MM-DD 00:00:00)

# filter by range using date part
mask = (daily["day"].dt.date >= date_start) & (daily["day"].dt.date <= date_end)
daily = daily.loc[mask].copy()

# ensure numeric
daily["weight_kg"] = pd.to_numeric(daily["weight_kg"], errors="coerce")
daily["steps"]     = pd.to_numeric(daily["steps"], errors="coerce")

# resample guarantees ONE ROW per calendar day (averages if multiple logs)
daily_day = (
    daily.set_index("day")
         .sort_index()
         .resample("D")
         .mean(numeric_only=True)
         .reset_index()
)

# derived km
daily_day["km_calc"] = steps_to_km(daily_day["steps"]).round(2)

# ---------- WEEKLY: filters + derived avg_km ----------
weekly_f = weekly.copy()
if not weekly_f.empty:
    for col in ("diet_score", "workout_score"):
        if col not in weekly_f.columns: weekly_f[col] = pd.NA
        weekly_f[col] = pd.to_numeric(weekly_f[col], errors="coerce")
    ds = weekly_f["diet_score"].fillna(10)
    ws = weekly_f["workout_score"].fillna(10)
    weekly_f = weekly_f[(ds >= adherence_min) & (ws >= adherence_min)]
    if "avg_steps" in weekly_f.columns:
        weekly_f["avg_km_calc"] = steps_to_km(weekly_f["avg_steps"]).round(2)

# ---------- KPIs ----------
kpi = st.columns(4)
with kpi[0]:
    st.markdown('<div class="card kpi">', unsafe_allow_html=True)
    st.markdown('<div class="label">Current Weight</div>', unsafe_allow_html=True)
    cur = daily_day["weight_kg"].dropna().iloc[-1] if daily_day["weight_kg"].notna().any() else None
    st.markdown(f'<div class="value">{cur:.1f} kg</div>' if cur is not None else '<div class="value">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with kpi[1]:
    st.markdown('<div class="card kpi">', unsafe_allow_html=True)
    st.markdown('<div class="label">7-day Avg Steps</div>', unsafe_allow_html=True)
    seven_steps = int(rolling_avg(daily_day["steps"].fillna(0), 7).iloc[-1]) if daily_day["steps"].notna().any() else None
    st.markdown(f'<div class="value">{seven_steps}</div>' if seven_steps is not None else '<div class="value">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with kpi[2]:
    st.markdown('<div class="card kpi">', unsafe_allow_html=True)
    st.markdown('<div class="label">7-day Avg KM (derived)</div>', unsafe_allow_html=True)
    seven_km = rolling_avg(daily_day["km_calc"].fillna(0), 7).iloc[-1] if daily_day["km_calc"].notna().any() else None
    st.markdown(f'<div class="value">{seven_km:.2f} km</div>' if seven_km is not None else '<div class="value">—</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
with kpi[3]:
    st.markdown('<div class="card kpi">', unsafe_allow_html=True)
    st.markdown('<div class="label">Days ≥ Step Goal</div>', unsafe_allow_html=True)
    good_days = int((daily_day["steps"] >= step_goal).sum()) if daily_day["steps"].notna().any() else 0
    st.markdown(f'<div class="value">{good_days}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


st.markdown("<br/>", unsafe_allow_html=True)

# ---------- Emoji sentiment for latest *available* weekly check-in ----------
if not weekly_f.empty:
    # choose newest row that actually has any KPI filled
    kpi_cols = ["sleep_issues", "hunger_issues", "stress_issues", "diet_score", "workout_score"]
    sort_col = "start_date" if "start_date" in weekly_f.columns else ("week_number" if "week_number" in weekly_f.columns else None)
    wf_sorted = weekly_f.sort_values(sort_col, kind="stable") if sort_col else weekly_f

    # keep rows where at least one KPI is present
    wf_nonempty = wf_sorted.copy()
    for c in kpi_cols:
        if c not in wf_nonempty.columns:
            wf_nonempty[c] = pd.NA
        wf_nonempty[c] = pd.to_numeric(wf_nonempty[c], errors="coerce")
    wf_nonempty = wf_nonempty.dropna(subset=kpi_cols, how="all")

    def _clean(v):
        """Return a plain Python float or None (never NaN)."""
        try:
            f = float(v)
            return None if pd.isna(f) else f
        except Exception:
            return None

    def _fmt(v, suffix=""):
        if v is None:
            return "—"
        if float(v).is_integer():
            return f"{int(v)}{suffix}"
        return f"{float(v):.1f}{suffix}"

    if not wf_nonempty.empty:
        l = wf_nonempty.iloc[-1]
        # materialize as clean primitives so formatting never shows '(nan)'
        v_sleep   = _clean(l.get("sleep_issues"))
        v_hunger  = _clean(l.get("hunger_issues"))
        v_stress  = _clean(l.get("stress_issues"))
        v_diet    = _clean(l.get("diet_score"))
        v_workout = _clean(l.get("workout_score"))

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f"**Sleep**<br/>{issue_emoji(v_sleep)} {_fmt(v_sleep)}", unsafe_allow_html=True)
        with c2:
            st.markdown(f"**Hunger**<br/>{issue_emoji(v_hunger)} {_fmt(v_hunger)}", unsafe_allow_html=True)
        with c3:
            st.markdown(f"**Stress**<br/>{issue_emoji(v_stress)} {_fmt(v_stress)}", unsafe_allow_html=True)
        with c4:
            st.markdown(f"**Diet**<br/>{adherence_emoji(v_diet)} {_fmt(v_diet, ' /10')}", unsafe_allow_html=True)
        with c5:
            st.markdown(f"**Workout**<br/>{adherence_emoji(v_workout)} {_fmt(v_workout, ' /10')}", unsafe_allow_html=True)
        st.markdown("<hr/>", unsafe_allow_html=True)

# ---------- Daily charts (x='day' ensures date axis; resample removed duplicates) ----------
if show_weight and daily_day["weight_kg"].notna().any():
    s = daily_day[["day", "weight_kg"]].copy()
    s["smooth"] = rolling_avg(s["weight_kg"], smooth)
    fig = px.line(s, x="day", y="smooth", markers=True, title="Daily Weight (smoothed)")
    rng = nice_y_range(s["smooth"])
    if rng:
        fig.update_yaxes(range=rng)
    else:
        # if all values identical or single point, give a small visual band
        v = float(s["smooth"].dropna().iloc[-1]) if s["smooth"].notna().any() else 0.0
        fig.update_yaxes(range=[v - 0.5, v + 0.5])
    fig.update_xaxes(dtick="D1", tickformat="%b %-d, %Y")
    st.plotly_chart(fig, use_container_width=True)

charts = []
if show_steps and daily_day["steps"].notna().any():
    charts.append(("Daily Steps", "steps", "bar"))
if show_km and daily_day["km_calc"].notna().any():
    charts.append(("Daily KM (derived from steps)", "km_calc", "line"))

if charts:
    cols = st.columns(len(charts))
    for idx, (title, col, kind) in enumerate(charts):
        fig = px.bar(daily_day, x="day", y=col, title=title) if kind == "bar" else \
              px.line(daily_day, x="day", y=col, markers=True, title=title)
        fig.update_xaxes(dtick="D1", tickformat="%b %-d, %Y")
        rng = nice_y_range(daily_day[col])
        if rng:
            fig.update_yaxes(range=rng)
        else:
            v = float(pd.to_numeric(daily_day[col], errors="coerce").dropna().iloc[-1]) if daily_day[col].notna().any() else 0.0
            pad = max(abs(v) * 0.1, 0.5)
            fig.update_yaxes(range=[v - pad, v + pad])
        cols[idx].plotly_chart(fig, use_container_width=True)

# ---------- Weekly charts ----------
if not weekly_f.empty:
    row = []
    if "avg_weight_kg" in weekly_f.columns and weekly_f["avg_weight_kg"].notna().any():
        row.append(px.line(weekly_f, x="week_number", y="avg_weight_kg", markers=True, title="Avg Weight by Week"))
    if "avg_steps" in weekly_f.columns and weekly_f["avg_steps"].notna().any():
        row.append(px.bar(weekly_f, x="week_number", y="avg_steps", title="Avg Steps by Week"))
    if row:
        cols = st.columns(len(row))
        for ci, fig in zip(cols, row):
            ci.plotly_chart(fig, use_container_width=True)

    row = []
    if show_weekly_loss and "weekly_weight_loss" in weekly_f.columns and weekly_f["weekly_weight_loss"].notna().any():
        row.append(px.bar(weekly_f, x="week_number", y="weekly_weight_loss", title="Weekly Weight Change (kg)"))
    if "avg_km_calc" in weekly_f.columns and weekly_f["avg_km_calc"].notna().any():
        row.append(px.line(weekly_f, x="week_number", y="avg_km_calc", markers=True, title="Avg KM by Week (derived)"))
    if row:
        cols = st.columns(len(row))
        for ci, fig in zip(cols, row):
            ci.plotly_chart(fig, use_container_width=True)

# ---------- Expenses summary & charts ----------
if 'expenses_df' in locals() and expenses_df is not None and not expenses_df.empty:
    expm = expense_metrics(expenses_df)
    # KPI: Total expenses till date
    total_exp = 0.0
    try:
        total_exp = float(expm.get("total", 0.0))
    except Exception:
        total_exp = 0.0

    kpi_exp = st.columns(1)
    with kpi_exp[0]:
        st.markdown('<div class="card kpi">', unsafe_allow_html=True)
        st.markdown('<div class="label">Total Health Expenses</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="value">₹{total_exp:,.0f}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Charts: Month-on-month and category split
    col_mom, col_cat = st.columns(2)

    by_month = expm.get("by_month") if isinstance(expm, dict) else None
    if isinstance(by_month, pd.DataFrame) and not by_month.empty:
        # Expect columns: month (period/str) and amount (numeric)
        bm = by_month.copy()
        # Coerce to datetime for ordering if needed
        if not pd.api.types.is_datetime64_any_dtype(bm.get("month")):
            with pd.option_context('mode.chained_assignment', None):
                try:
                    bm["month"] = pd.to_datetime(bm["month"].astype(str))
                except Exception:
                    pass
        fig_m = px.bar(bm, x="month", y="amount", title="Monthly Health Expenses")
        fig_m.update_xaxes(dtick="M1", tickformat="%b %Y")
        col_mom.plotly_chart(fig_m, use_container_width=True)

    by_cat = expm.get("by_category") if isinstance(expm, dict) else None
    if isinstance(by_cat, pd.DataFrame) and not by_cat.empty:
        bc = by_cat.copy()
        fig_c = px.pie(bc, names="category", values="amount", title="Expenses by Category")
        col_cat.plotly_chart(fig_c, use_container_width=True)

# ---------- Tables ----------
if show_tables:
    st.subheader("Daily Data (raw)")
    st.dataframe(daily_raw.sort_values("date"), use_container_width=True)
    st.subheader("Weekly Data")
    wk_tbl = weekly.copy()
    if "week_number" in wk_tbl.columns:
        wk_tbl["week_number"] = pd.to_numeric(wk_tbl["week_number"], errors="coerce")
        wk_tbl = wk_tbl.sort_values("week_number")
    st.dataframe(wk_tbl, use_container_width=True)
