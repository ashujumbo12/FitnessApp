import streamlit as st
from pathlib import Path
from db import init_db, get_session
from models import User

# --- Streamlit config must be first ---
st.set_page_config(page_title="Fitness Progress", page_icon="📈", layout="wide")

# --- Load CSS (shared helper) ---
# Be robust whether this file is run as a script or as a package module
try:
    from utils import load_css  # when executed with: streamlit run fitness_dashboard_app/app.py
except Exception:
    try:
        from .utils import load_css  # when imported as a package module
    except Exception:
        # Last-resort no-op so the app never crashes due to styling import
        def load_css():
            return None

load_css()

# --- DB bootstrap ---
init_db()

def bootstrap_user() -> User:
    """Ensure a single local user exists and return it."""
    from sqlmodel import select
    with get_session() as sess:
        u = sess.exec(select(User)).first()
        if not u:
            u = User(name="You", email=None, height_cm=None, goal_weight_kg=None, units="metric")
            sess.add(u)
            sess.commit()
            sess.refresh(u)
        return u

user = bootstrap_user()

# --- Sidebar: profile ---
st.sidebar.header("Profile")
with st.sidebar:
    with st.form("profile_form"):
        name = st.text_input("Name", user.name or "You")
        height = st.number_input(
            "Height (cm)",
            value=float(user.height_cm) if user.height_cm else 0.0,
            min_value=0.0,
            step=0.5,
            help="Enter height in centimeters. (Unit selection below affects display elsewhere.)",
        )
        goal = st.number_input(
            "Goal weight (kg)",
            value=float(user.goal_weight_kg) if user.goal_weight_kg else 0.0,
            min_value=0.0,
            step=0.1,
        )
        current_units = (user.units or "metric").lower()
        units = st.selectbox("Units", ["metric", "imperial"], index=0 if current_units == "metric" else 1)
        if st.form_submit_button("Save profile"):
            with get_session() as sess:
                user.name = name
                user.height_cm = height or None
                user.goal_weight_kg = goal or None
                user.units = units
                sess.add(user)
                sess.commit()
            st.success("Profile saved")

# --- Home content ---
st.title("📈 Fitness Progress — Home")
st.write("Use the tabs in the left sidebar (Pages) to add entries and explore your dashboard.")

st.markdown('<div class="card">', unsafe_allow_html=True)
st.subheader("Getting started")
st.markdown(
    """
1. Go to **Data Entry** to log your **Daily** (weight/steps) and **Weekly** (measurements, scores) data.  
2. Open **Dashboard** to see KPIs, trends, and comparisons.  
3. Import your existing sheet via **Import/Export**.  
    """
)
st.markdown("</div>", unsafe_allow_html=True)

st.caption("All data stays on your machine (SQLite).")
