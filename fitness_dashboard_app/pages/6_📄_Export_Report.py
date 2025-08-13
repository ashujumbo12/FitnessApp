# pages/6_📄_Export_Report.py
import io
import datetime as dt
import streamlit as st
import pandas as pd

# Try optional deps up front but don't crash the page
_missing = []

try:
    import plotly.express as px
    import plotly.io as pio
except Exception as e:
    px = None
    _missing.append("plotly")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.units import cm
except Exception:
    A4 = canvas = ImageReader = cm = None
    _missing.append("reportlab")

from sqlmodel import select
from db import get_session
from models import User
from utils import load_daily_df, load_weekly_df, rolling_avg

st.set_page_config(page_title="📄 Export Report", page_icon="📄", layout="wide")
st.title("📄 Export Progress Report")

# --- helper ---
def steps_to_km(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    return (s * 8.0) / (1780.0 * 5.0)

# --- load data (never crash silently) ---
try:
    with get_session() as sess:
        user = sess.exec(select(User)).first()
        daily = load_daily_df(sess, user.id) if user else pd.DataFrame()
        weekly = load_weekly_df(sess, user.id) if user else pd.DataFrame()
except Exception as e:
    st.error("Failed to load data.")
    st.exception(e)
    st.stop()

if daily.empty:
    st.info("No daily data to export yet. Add entries in **📝 Data Entry**.")
    st.stop()

# --- range picker ---
min_d = pd.to_datetime(daily["date"]).dt.date.min()
max_d = pd.to_datetime(daily["date"]).dt.date.max()
dr = st.date_input("Date range", value=(min_d, max_d))

# --- prepare day-level frame (same logic as dashboard) ---
d = daily.copy()
d["day"] = pd.to_datetime(d["date"], utc=True, errors="coerce").dt.normalize()
d = d[(d["day"].dt.date >= dr[0]) & (d["day"].dt.date <= dr[1])]
d["weight_kg"] = pd.to_numeric(d["weight_kg"], errors="coerce")
d["steps"] = pd.to_numeric(d["steps"], errors="coerce")
day = (
    d.set_index("day")
     .sort_index()
     .resample("D")
     .mean(numeric_only=True)
     .reset_index()
)
day["km_calc"] = steps_to_km(day["steps"]).round(2)

# Quick stats
c1, c2, c3 = st.columns(3)
with c1: st.metric("Days in range", len(day))
with c2: st.metric("Avg Weight (kg)", f"{day['weight_kg'].mean():.2f}" if day["weight_kg"].notna().any() else "—")
with c3: st.metric("Avg Steps", f"{int(day['steps'].mean()):,}" if day["steps"].notna().any() else "—")

# --- Charts (if plotly present) ---
figs = []
if px is None:
    st.warning("Charts disabled because **plotly** isn’t installed. Install with: `pip install plotly kaleido`")
else:
    # Weight (smoothed)
    s = day[["day", "weight_kg"]].copy()
    s["smooth"] = rolling_avg(s["weight_kg"], 7)
    fig1 = px.line(s, x="day", y="smooth", title="Daily Weight (smoothed)", markers=True)
    fig1.update_xaxes(dtick="D1", tickformat="%b %-d, %Y")
    figs.append(("weight.png", fig1))

    # Steps
    fig2 = px.bar(day, x="day", y="steps", title="Daily Steps")
    fig2.update_xaxes(dtick="D1", tickformat="%b %-d, %Y")
    figs.append(("steps.png", fig2))

    # KM
    fig3 = px.line(day, x="day", y="km_calc", title="Daily KM (derived)", markers=True)
    fig3.update_xaxes(dtick="D1", tickformat="%b %-d, %Y")
    figs.append(("km.png", fig3))

    # Weekly change if available
    if not weekly.empty and "weekly_weight_loss" in weekly.columns:
        fig4 = px.bar(weekly, x="week_number", y="weekly_weight_loss", title="Weekly Weight Change (kg)")
        figs.append(("weekly_change.png", fig4))

    # Show preview inline
    st.subheader("Preview")
    grid = st.columns(min(3, len(figs)) or 1)
    for i, (_, fig) in enumerate(figs):
        grid[i % len(grid)].plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- Export buttons ---
col_png, col_pdf = st.columns(2)

with col_png:
    if px is None:
        st.button("⬇️ Download Charts (PNG, ZIP)", disabled=True)
        st.caption("Install: `pip install plotly kaleido`")
    else:
        # Try to create PNGs via kaleido; show error if missing
        if "kaleido" in _missing:
            st.button("⬇️ Download Charts (PNG, ZIP)", disabled=True)
            st.caption("Install: `pip install kaleido`")
        else:
            try:
                import zipfile
                png_zip = io.BytesIO()
                with zipfile.ZipFile(png_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                    for name, fig in figs:
                        img_bytes = fig.to_image(format="png", scale=2)  # requires kaleido
                        zf.writestr(name, img_bytes)
                png_zip.seek(0)
                st.download_button(
                    "⬇️ Download Charts (PNG, ZIP)",
                    data=png_zip.getvalue(),
                    file_name=f"fitness_charts_{dt.date.today()}.zip",
                    mime="application/zip",
                )
            except Exception as e:
                st.error("Couldn’t create PNGs (is **kaleido** installed?)")
                st.exception(e)

with col_pdf:
    if A4 is None or canvas is None:
        st.button("⬇️ Download PDF Report", disabled=True)
        st.caption("Install: `pip install reportlab`")
    elif px is None:
        st.button("⬇️ Download PDF Report", disabled=True)
        st.caption("Install: `pip install plotly kaleido`")
    else:
        try:
            # Build PDF
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            W, H = A4

            # cover
            c.setFont("Helvetica-Bold", 18)
            c.drawString(2*cm, H-2.5*cm, "Fitness Progress Report")
            c.setFont("Helvetica", 12)
            who = getattr(user, "name", "You")
            c.drawString(2*cm, H-3.5*cm, f"User: {who}")
            c.drawString(2*cm, H-4.1*cm, f"Range: {dr[0]} → {dr[1]}")
            c.drawString(2*cm, H-4.7*cm, f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
            c.showPage()

            def add_plot(fig, title):
                png = fig.to_image(format="png", scale=2)  # kaleido
                img = ImageReader(io.BytesIO(png))
                c.setFont("Helvetica-Bold", 14)
                c.drawString(2*cm, H-2.0*cm, title)
                iw, ih = img.getSize()
                maxw, maxh = W-3*cm, H-4*cm
                ratio = min(maxw/iw, maxh/ih)
                w, h = iw*ratio, ih*ratio
                c.drawImage(img, (W-w)/2, (H-h)/2-1*cm, width=w, height=h, preserveAspectRatio=True, mask='auto')
                c.showPage()

            # Add charts
            for name, fig in figs:
                title = {
                    "weight.png": "Daily Weight (smoothed)",
                    "steps.png": "Daily Steps",
                    "km.png": "Daily KM (derived)",
                    "weekly_change.png": "Weekly Weight Change",
                }.get(name, name)
                add_plot(fig, title)

            c.save()
            buf.seek(0)
            st.download_button(
                "⬇️ Download PDF Report",
                data=buf.getvalue(),
                file_name=f"fitness_report_{dt.date.today()}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error("Couldn’t create PDF.")
            st.exception(e)
