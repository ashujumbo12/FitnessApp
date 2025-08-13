# utils.py
# Robust helpers for loading daily/weekly dataframes, and a safe CSS loader.

from pathlib import Path
import streamlit as st
from sqlmodel import Session, select
import pandas as pd
from models import DailyMetric, Week, Measurement, Wellbeing, Adherence


# ---- UI helpers --------------------------------------------------------------

def load_css(relative_path: str = "assets/style.css", show_warning: bool = False) -> None:
    """Safely load CSS regardless of where Streamlit executes the page.

    - Tries multiple candidate locations relative to this file and the CWD.
    - Never raises; optionally shows a small warning if show_warning=True.
    - Default is silent (no warnings) to avoid noisy UIs.
    """
    here = Path(__file__).resolve().parent

    # Candidate search locations (first hit wins)
    candidates = [
        here / relative_path,                                  # fitness_dashboard_app/assets/style.css
        here.parent / relative_path,                           # project_root/assets/style.css (fallback)
        Path.cwd() / "fitness_dashboard_app" / relative_path,  # CWD/fitness_dashboard_app/assets/style.css
        Path.cwd() / relative_path,                            # CWD/assets/style.css
    ]

    css_file = next((p for p in candidates if p.exists()), None)
    if not css_file:
        if show_warning:
            st.caption(
                "Warning: stylesheet not found (looked for: "
                + ", ".join(str(p) for p in candidates)
                + ")"
            )
        return

    try:
        st.markdown(f"<style>{css_file.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    except Exception:
        # Never break the app due to styling issues
        if show_warning:
            st.caption(f"Warning: failed to load stylesheet at {css_file}")
        return


# ---- Defaults to keep the dashboard stable even with missing data ----
REQUIRED_WEEKLY_COLS = [
    "week_id", "week_number", "start_date",
    "avg_weight_kg", "avg_steps", "weekly_weight_loss",
    "diet_score", "workout_score",
    "sleep_issues", "hunger_issues", "stress_issues",
    "waist_navel_in", "chest_in", "r_biceps_in", "l_biceps_in", "r_thigh_in", "l_thigh_in",
]


def _ensure_weekly_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee the weekly DF has all expected columns."""
    if df is None or df.empty:
        # Return an empty frame with every column present so downstream code won’t KeyError
        out = pd.DataFrame()
        for c in REQUIRED_WEEKLY_COLS:
            out[c] = pd.Series(dtype="float64")
        return out
    for c in REQUIRED_WEEKLY_COLS:
        if c not in df.columns:
            df[c] = pd.NA
    return df


def _to_dict(obj):
    """Works for Pydantic v2 (model_dump) and v1 (dict), else fallback."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj.__dict__)


# ---- Public API ---------------------------------------------------------------

def load_daily_df(sess: Session, user_id: int) -> pd.DataFrame:
    """Return a dataframe of daily metrics for a user."""
    rows = sess.exec(select(DailyMetric).where(DailyMetric.user_id == user_id)).all()
    if not rows:
        return pd.DataFrame(columns=["id", "user_id", "date", "week_id", "weight_kg", "steps", "run_km"])
    df = pd.DataFrame([_to_dict(r) for r in rows])
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_weekly_df(sess: Session, user_id: int) -> pd.DataFrame:
    """
    Build a weekly dataframe with:
      - avg_weight_kg, avg_steps (from dailies)
      - weekly_weight_loss (diff of avg weight)
      - merged weekly tables: measurements, wellbeing, adherence
    """
    d = load_daily_df(sess, user_id)
    if d.empty:
        return _ensure_weekly_cols(pd.DataFrame())

    # Base week table
    weeks = sess.exec(select(Week).where(Week.user_id == user_id)).all()
    w = pd.DataFrame([_to_dict(x) for x in weeks]) if weeks else pd.DataFrame(columns=["id", "user_id", "week_number", "start_date"])

    # Weekly aggregates from dailies
    if "week_id" not in d.columns:
        return _ensure_weekly_cols(pd.DataFrame())

    avg = (
        d.groupby("week_id", dropna=False)
        .agg(avg_weight_kg=("weight_kg", "mean"), avg_steps=("steps", "mean"))
        .reset_index()
    )

    # Merge with weeks to get week_number/start_date
    if not w.empty:
        out = avg.merge(
            w[["id", "week_number", "start_date"]],
            left_on="week_id", right_on="id", how="left"
        ).drop(columns=["id"])
    else:
        out = avg.copy()
        out["week_number"] = pd.NA
        out["start_date"] = pd.NA

    # Optional weekly tables
    def table_df(model_cls, cols):
        rows = sess.exec(select(model_cls).where(model_cls.user_id == user_id)).all()
        return pd.DataFrame([_to_dict(r) for r in rows]) if rows else pd.DataFrame(columns=["id", "user_id", "week_id"] + cols)

    m = table_df(Measurement, ["r_biceps_in", "l_biceps_in", "chest_in", "r_thigh_in", "l_thigh_in", "waist_navel_in"])
    wb = table_df(Wellbeing, ["sleep_issues", "hunger_issues", "stress_issues"])
    ad = table_df(Adherence, ["diet_score", "workout_score"])

    for frame in (m, wb, ad):
        if not frame.empty:
            # Keep only one row per week_id if duplicates exist
            frame = frame.sort_values(by="id").drop_duplicates(subset=["week_id"], keep="last")
            out = out.merge(
                frame.drop(columns=[c for c in ["id", "user_id"] if c in frame.columns]),
                on="week_id",
                how="left",
            )

    # Order and derived fields
    if "week_number" in out.columns:
        out = out.sort_values("week_number", na_position="last")
    out["weekly_weight_loss"] = out["avg_weight_kg"].diff(1)

    # Ensure all expected columns exist
    out = _ensure_weekly_cols(out)
    return out


def rolling_avg(series: pd.Series, window: int = 7) -> pd.Series:
    """7-day rolling average with graceful handling for short series."""
    return series.rolling(window=window, min_periods=1).mean()
