"""
2_corridor_detail.py — AAM Corridor Detail View (Streamlit page)

Single OD pair drill-down: corridor metadata, key metrics, 24-hour temporal profile.
Adapted from app_corridor_detail.py — config dependency removed, helpers from utils.py.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import (
    inject_css,
    build_kpi_html,
    build_info_html,
    build_badge_html,
    format_percent,
    format_distance,
    format_int,
    format_coord,
    get_first_value,
    safe_filename,
    to_csv_bytes,
    chart_header,
)

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Info text for chart popovers
# ---------------------------------------------------------------------------

INFO_OVERVIEW = (
    "Summary of the selected origin–destination pair. **Corridor Details** shows LGA names, "
    "suburb, tourism region, and centroid coordinates. **Corridor Metrics** shows total "
    "trips and unique devices observed, average trip distance, and weekday vs weekend share. "
    "Use the sidebar to switch between any origin–destination pair in the dataset."
)
INFO_TEMPORAL_P2 = (
    "Hourly trip distribution for the selected corridor, split by Weekday and Weekend. "
    "**Hourly Chart tab:** line chart for visual comparison of travel rhythms. "
    "**Hourly Pivot Table tab:** exact counts per hour (24 rows). "
    "**Raw Temporal Records tab:** underlying data rows with hour, day type, and peak period columns. "
    "High AM/PM peaks suggest commuter or structured travel; flat profiles suggest leisure trips."
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_OUTPUT_DIR      = Path(__file__).parent.parent / "output"
RANKED_CSV       = str(_OUTPUT_DIR / "ranked_corridors.csv")
TEMPORAL_ALL_CSV = str(_OUTPUT_DIR / "temporal_distribution_all.csv")

PCT_COLS  = ["pct_weekday", "pct_weekday_am_peak", "pct_weekday_pm_peak",
             "pct_weekend", "pct_weekend_am_peak", "pct_weekend_pm_peak"]
DIST_COLS = ["avg_distance_km"]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading corridor data...")
def load_data(ranked_path: str, temporal_all_path: str):
    missing = []
    if not os.path.exists(ranked_path):
        missing.append(f"`{ranked_path}`")
    if not os.path.exists(temporal_all_path):
        missing.append(f"`{temporal_all_path}`")

    if missing:
        return None, None, (
            "Pipeline output CSV(s) not found: " + ", ".join(missing) + ". "
            "Re-run the pipeline to generate them."
        )

    ranked_df = pd.read_csv(ranked_path)
    temporal_all_df = pd.read_csv(temporal_all_path)
    return ranked_df, temporal_all_df, None


# ---------------------------------------------------------------------------
# CSS + page header
# ---------------------------------------------------------------------------

inject_css()

st.title("Localis FullDelivary — Single Corridor Deep Dive")
st.caption("Localis FullDelivary — Victoria LGA Origin–Destination Analysis")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

ranked_df, temporal_df, load_error = load_data(RANKED_CSV, TEMPORAL_ALL_CSV)

if load_error:
    st.error(load_error)
    st.stop()

required_ranked_cols = {"origin_lga", "dest_lga"}
required_temporal_cols = {"origin_lga", "dest_lga", "hour_of_day", "day_type", "n_trips"}

if not required_ranked_cols.issubset(ranked_df.columns):
    st.error("ranked_corridors CSV is missing one or more required columns.")
    st.stop()

if not required_temporal_cols.issubset(temporal_df.columns):
    st.error("temporal_distribution CSV is missing one or more required columns.")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Filters")

    state = st.text_input("State", value="Victoria")

    origin_lgas = sorted(ranked_df["origin_lga"].dropna().unique())
    origin = st.selectbox("Origin LGA", origin_lgas)

    dest_lgas = sorted(
        ranked_df.loc[ranked_df["origin_lga"] == origin, "dest_lga"]
        .dropna()
        .unique()
    )
    dest = st.selectbox("Destination LGA", dest_lgas)

# ---------------------------------------------------------------------------
# Selected OD pair
# ---------------------------------------------------------------------------

od_mask = (ranked_df["origin_lga"] == origin) & (ranked_df["dest_lga"] == dest)
od_row = ranked_df[od_mask].reset_index(drop=True)

if od_row.empty:
    st.warning("No corridor data found for this OD pair.")
    st.stop()

od_temporal = temporal_df[
    (temporal_df["origin_lga"] == origin) & (temporal_df["dest_lga"] == dest)
].reset_index(drop=True)

origin_safe = safe_filename(origin)
dest_safe = safe_filename(dest)

# ---------------------------------------------------------------------------
# Extract summary values
# ---------------------------------------------------------------------------

origin_lga = str(get_first_value(od_row, "origin_lga", "N/A"))
dest_lga = str(get_first_value(od_row, "dest_lga", "N/A"))
origin_suburb = str(get_first_value(od_row, "origin_suburb", "N/A"))
dest_suburb = str(get_first_value(od_row, "dest_suburb", "N/A"))
origin_region = str(get_first_value(od_row, "origin_tourism_region", "N/A"))
dest_region = str(get_first_value(od_row, "dest_tourism_region", "N/A"))

origin_centroid = format_coord(
    get_first_value(od_row, "origin_centroid_lat"),
    get_first_value(od_row, "origin_centroid_lon"),
)
dest_centroid = format_coord(
    get_first_value(od_row, "dest_centroid_lat"),
    get_first_value(od_row, "dest_centroid_lon"),
)

total_trips_raw = get_first_value(od_row, "n_trips")
unique_devices_raw = get_first_value(od_row, "n_devices")
avg_distance_raw = get_first_value(od_row, "avg_distance_km")
pct_weekday_raw = get_first_value(od_row, "pct_weekday")

total_trips = format_int(total_trips_raw)
unique_devices = format_int(unique_devices_raw)
avg_distance = format_distance(avg_distance_raw)
pct_weekday = format_percent(pct_weekday_raw)

pct_weekend_raw = get_first_value(od_row, "pct_weekend")
weekend_share_value = format_percent(pct_weekend_raw)


# ---------------------------------------------------------------------------
# Corridor overview
# ---------------------------------------------------------------------------

chart_header("Corridor Overview", INFO_OVERVIEW, h3=True)

details_col, metrics_col = st.columns([1.55, 1.0])

with details_col:
    st.markdown('<div class="subsection-title">Corridor Details</div>', unsafe_allow_html=True)

    details_left, details_right = st.columns(2)

    with details_left:
        st.markdown(build_info_html("Origin LGA", origin_lga), unsafe_allow_html=True)
        st.markdown(build_info_html("Origin suburb", origin_suburb), unsafe_allow_html=True)
        st.markdown(build_info_html("Origin tourism region", origin_region), unsafe_allow_html=True)
        st.markdown(build_info_html("Origin centroid", origin_centroid), unsafe_allow_html=True)

    with details_right:
        st.markdown(build_info_html("Destination LGA", dest_lga), unsafe_allow_html=True)
        st.markdown(build_info_html("Destination suburb", dest_suburb), unsafe_allow_html=True)
        st.markdown(build_info_html("Destination tourism region", dest_region), unsafe_allow_html=True)
        st.markdown(build_info_html("Destination centroid", dest_centroid), unsafe_allow_html=True)

with metrics_col:
    st.markdown('<div class="subsection-title">Corridor Metrics</div>', unsafe_allow_html=True)

    metric_row1_col1, metric_row1_col2 = st.columns(2)
    metric_row2_col1, metric_row2_col2 = st.columns(2)
    metric_row3_col1, metric_row3_col2 = st.columns(2)

    with metric_row1_col1:
        st.markdown(build_badge_html("Total trips", total_trips), unsafe_allow_html=True)
    with metric_row1_col2:
        st.markdown(build_badge_html("Unique devices", unique_devices), unsafe_allow_html=True)
    with metric_row2_col1:
        st.markdown(build_badge_html("Avg distance", avg_distance), unsafe_allow_html=True)
    with metric_row2_col2:
        st.markdown(build_badge_html("Weekday share", pct_weekday), unsafe_allow_html=True)
    with metric_row3_col1:
        st.markdown(build_badge_html("Weekend share", weekend_share_value), unsafe_allow_html=True)
    with metric_row3_col2:
        st.empty()

with st.expander("View raw corridor record", expanded=False):
    col_cfg = {}
    for c in PCT_COLS:
        if c in od_row.columns:
            col_cfg[c] = st.column_config.NumberColumn(c, format="%.1f %%")
    for c in DIST_COLS:
        if c in od_row.columns:
            col_cfg[c] = st.column_config.NumberColumn(c, format="%.2f km")
    if "n_trips" in od_row.columns:
        col_cfg["n_trips"] = st.column_config.NumberColumn("n_trips", format="%d")
    if "n_devices" in od_row.columns:
        col_cfg["n_devices"] = st.column_config.NumberColumn("n_devices", format="%d")

    st.dataframe(
        od_row,
        use_container_width=True,
        column_config=col_cfg,
        hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Temporal profile section
# ---------------------------------------------------------------------------

chart_header("24-Hour Temporal Profile", INFO_TEMPORAL_P2, h3=True)

if od_temporal.empty:
    st.info("No temporal data recorded for this OD pair.")
else:
    pivot = (
        od_temporal
        .groupby(["hour_of_day", "day_type"], dropna=False)["n_trips"]
        .sum()
        .unstack(level="day_type", fill_value=0)
        .reindex(range(24), fill_value=0)
    )
    pivot.index.name = "Hour of Day"

    for col in ["Weekday", "Weekend"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot[["Weekday", "Weekend"]]
    chart_df = pivot.reset_index()

    total_weekday = int(chart_df["Weekday"].sum())
    total_weekend = int(chart_df["Weekend"].sum())

    note_cols = st.columns([1.0, 1.0, 1.9])
    with note_cols[0]:
        st.markdown(build_badge_html("Weekday trips", f"{total_weekday:,}"), unsafe_allow_html=True)
    with note_cols[1]:
        st.markdown(build_badge_html("Weekend trips", f"{total_weekend:,}"), unsafe_allow_html=True)
    with note_cols[2]:
        observed_note = f"Observed trips in temporal profile: {format_int(total_trips_raw)}"
        st.markdown(f'<div class="chart-note">{observed_note}</div>', unsafe_allow_html=True)

    chart_tab, pivot_tab, raw_tab = st.tabs(
        ["Hourly Chart", "Hourly Pivot Table", "Raw Temporal Records"]
    )

    with chart_tab:
        st.caption("Hourly trip distribution for the selected corridor")
        chart_plot_df = chart_df.rename(columns={"Hour of Day": "hour_of_day"})
        st.line_chart(
            chart_plot_df.set_index("hour_of_day")[["Weekday", "Weekend"]],
            use_container_width=True,
            height=360,
        )

    with pivot_tab:
        pivot_cfg = {
            "Hour of Day": st.column_config.NumberColumn("Hour of Day", format="%d:00"),
            "Weekday": st.column_config.NumberColumn("Weekday Trips", format="%d"),
            "Weekend": st.column_config.NumberColumn("Weekend Trips", format="%d"),
        }

        st.dataframe(
            chart_df,
            use_container_width=True,
            column_config=pivot_cfg,
            hide_index=True,
            height=830,
        )

    with raw_tab:
        st.dataframe(
            od_temporal,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

st.divider()

# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

st.markdown("### Downloads")

download_col1, download_col2 = st.columns(2)

with download_col1:
    st.download_button(
        label="Download Corridor Summary CSV",
        data=to_csv_bytes(od_row),
        file_name=f"corridor_summary_{origin_safe}_{dest_safe}.csv",
        mime="text/csv",
    )

with download_col2:
    if od_temporal.empty:
        st.button("Download Full Temporal Profile CSV", disabled=True)
    else:
        st.download_button(
            label="Download Full Temporal Profile CSV",
            data=to_csv_bytes(od_temporal),
            file_name=f"temporal_profile_full_{origin_safe}_{dest_safe}.csv",
            mime="text/csv",
        )
