# pages/7_💸_Expenses.py
import streamlit as st
import pandas as pd
from datetime import date
from sqlmodel import select
from db import get_session
from models import User, Expense
from utils import load_css, DEFAULT_EXPENSE_CATEGORIES, load_expenses_df, expense_metrics

st.set_page_config(page_title="💸 Expenses", page_icon="💸", layout="wide")
load_css(show_warning=False)

st.title("💸 Health Expenses")

with get_session() as sess:
    user = sess.exec(select(User)).first()

# --- Entry form ---
with st.form("add_expense", clear_on_submit=True):
    c1, c2, c3 = st.columns([1,1,2])
    with c1:
        d = st.date_input("Date", value=date.today())
        amt = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f")
    with c2:
        cat = st.selectbox("Category", DEFAULT_EXPENSE_CATEGORIES)
        other = st.text_input("Or enter custom category")
    with c3:
        note = st.text_area("Note (optional)", height=70, placeholder="e.g., Vitamin D3, monthly gym fee, physio session...")

    submitted = st.form_submit_button("Add Expense")
    if submitted:
        final_cat = other.strip() if other.strip() else cat
        with get_session() as sess:
            row = Expense(user_id=user.id, date=pd.to_datetime(d).date(), amount=float(amt), category=final_cat, note=note or None)
            sess.add(row)
            sess.commit()
        st.success("Expense added!")

st.divider()

# --- Listing & quick stats ---
with get_session() as sess:
    df = load_expenses_df(sess, user.id)

# --- normalize types for safe .dt / math ---
if df is None or df.empty:
    df = pd.DataFrame(columns=["date", "amount", "category", "note"])

df["date"] = pd.to_datetime(df["date"], errors="coerce")
df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
df = df.dropna(subset=["date"])  # remove rows without a valid date

metrics = expense_metrics(df) if callable(expense_metrics) else {}

c1, c2, c3 = st.columns([1,1,2])
with c1:
    total_all = float(metrics.get("total", df["amount"].sum()))
    st.metric("Total spend (all time)", f"₹ {total_all:,.0f}")
with c2:
    last_30 = df[df["date"] >= (pd.Timestamp.today() - pd.Timedelta(days=30))]
    st.metric("Last 30 days", f"₹ {last_30['amount'].sum():,.0f}")
with c3:
    cur_period = pd.Timestamp.today().to_period("M")
    month_period = df["date"].dt.to_period("M")
    this_month = df[month_period == cur_period]
    st.metric("This month", f"₹ {this_month['amount'].sum():,.0f}")

st.subheader("All expenses")
st.dataframe(
    df.sort_values("date", ascending=False),
    use_container_width=True,
    hide_index=True
)