from __future__ import annotations
import streamlit as st
from utils import load_css

# Streamlit page config MUST be the first Streamlit command on the page
st.set_page_config(page_title="⚙️ Settings", page_icon="⚙️", layout="wide")

# Load global CSS (robust path resolution handled inside utils.load_css)
load_css()  # defaults to "assets/style.css" at app root

st.title("⚙️ Settings")

with st.expander("Theme options"):
    st.write("Add theme toggles here.")