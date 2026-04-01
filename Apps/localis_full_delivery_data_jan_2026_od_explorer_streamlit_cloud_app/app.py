"""
app.py — Entry point for the unified AAM Victoria Passenger App (Streamlit)

This file owns the only st.set_page_config call for the entire app.
All page content lives in pages/.

Run:
    cd vic_trip_topn_localis_sample_app
    streamlit run localis_sampledata_passenger_cloud_app/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Localis FullDelivary(Data: Only Jan 2026) — Passenger App",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pg = st.navigation([
    st.Page("pages/1_od_overview.py",       title="Network Flow Map & Rankings", icon="🗺️"),
    st.Page("pages/2_corridor_detail.py",   title="Single Corridor Deep Dive",   icon="🔍"),
    st.Page("pages/3_trip_explorer.py",     title="Browse Raw Trip Records",     icon="📋"),
    st.Page("pages/4_corridor_explorer.py", title="Live Corridor Statistics",    icon="🛣️"),
])
pg.run()
