# =============================================================================
# 4_corridor_explorer.py — OD Corridor Explorer (Streamlit page)
#
# Visualises OD corridor flows from trip-level pipeline output.
# Adapted from app_trip_explorer_od_corridor.py — path corrected for new depth.
#
# Data source (sidebar toggle):
#   CSV     — output/trips_20GB.csv
#   Parquet — output/trips.parquet (default)
# =============================================================================

import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import chart_header

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Paths / sampling config
# ---------------------------------------------------------------------------
APP_DIR      = Path(__file__).parent
OUTPUT_DIR   = APP_DIR.parent / "output"
CSV_PATH     = OUTPUT_DIR / "trips_50MB.csv"
PARQUET_PATH = OUTPUT_DIR / "trips.parquet"

LARGE_FILE_THRESHOLD    = 500 * 1024 * 1024
SAMPLE_ROWS             = 500_000
DOWNLOAD_SIZE_THRESHOLD = 150 * 1024 * 1024

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

INFO_MAP_P4 = (
    "Geographic flow lines connecting origin and destination LGA centroids for the top N "
    "corridors. Line width and opacity scale with trip count — thicker/brighter = more trips. "
    "Blue dots = origin LGAs; orange dots = destination LGAs. "
    "Hover over midpoints for corridor name, trip count, and average distance. "
    "Adjust 'Top N Corridors on Map' in the sidebar to show more or fewer arcs."
)
INFO_TOP20 = (
    "Horizontal bar chart of the 20 busiest origin–destination pairs by trip count. "
    "Colour = average trip distance (darker blue = longer). Hover for exact values. "
    "**Use this** to identify the highest-volume markets within the filtered date range and region."
)
INFO_DAILY = (
    "Total trip count per calendar day across the filtered dataset. "
    "Use to spot seasonal trends, public holidays, or data anomalies (sudden drops may indicate "
    "missing data). Combine with the date range filter to zoom in on specific periods."
)
INFO_DOW_P4 = (
    "Trip counts broken down by day of week for the filtered corridor set. "
    "Shows whether this market is weekday (commuter/business) or weekend (leisure/tourism) dominant. "
    "A relatively flat profile across all days suggests mixed or event-driven demand."
)
INFO_HEAT = (
    "Cross-tabulation of trips by day of week (rows) and hour of day (columns). "
    "Dark cells = high trip volume at that time slot. "
    "**AM peak band (07–09)** and **PM peak band (16–18)** appearing on weekdays indicate "
    "commuter demand. Weekend peaks at mid-morning or afternoon indicate leisure travel. "
    "Use this to prioritise which time slots need the most capacity."
)
INFO_REGION_DIST = (
    "Average trip distance (km) for trips originating from each tourism region, "
    "with colour indicating number of trips (darker green = more trips). "
    "Regions with **high distance and high trips** are prime long-haul markets. "
    "Regions with **low distance** may be better served by ground transport."
)
INFO_MATRIX_P4 = (
    "Top 10 origin × top 10 destination LGA matrix. Cell values and colour = trip count. "
    "Diagonal cells (same LGA) are excluded. "
    "**Use this** to identify the densest sub-network and prioritise which city-pairs "
    "to operate routes on within the filtered tourism region and date range."
)
INFO_PEAK = (
    "Percentage of each corridor's trips occurring during AM peak (07–09) or PM peak (16–18), "
    "split into Weekday and Weekend panels. "
    "A high weekday peak share (>20%) indicates structured commuter demand. "
    "A high weekend peak share may indicate day-tripper or event-driven travel patterns. "
    "Use to size peak vs off-peak capacity requirements."
)
INFO_SPLIT = (
    "Stacked bar showing what percentage of each corridor's trips occur on weekdays vs weekends. "
    "**>60% weekend** = tourism or leisure-led corridor — demand sensitive to school holidays. "
    "**>60% weekday** = employment, education, or service travel — more predictable demand. "
    "Use alongside the Peak Hour Share chart to build a full demand profile for each corridor."
)

# ---------------------------------------------------------------------------
# Data loading (cached per source)
# ---------------------------------------------------------------------------
def _fix_date(df: pd.DataFrame) -> pd.DataFrame:
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["date"] = df["date"].dt.date
    return df


@st.cache_data
def load_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    return _fix_date(pd.read_csv(path, nrows=nrows))


@st.cache_data
def load_parquet(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if nrows is not None:
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(path)
        chunks, total = [], 0
        for batch in pf.iter_batches(batch_size=100_000):
            chunks.append(batch.to_pandas())
            total += len(chunks[-1])
            if total >= nrows:
                break
        df = pd.concat(chunks).head(nrows)
    else:
        df = pd.read_parquet(path)
    return _fix_date(df)


# ---------------------------------------------------------------------------
# Sidebar — Data source
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛣️ Live Corridor Statistics")
    st.divider()

    st.markdown("#### 💾 Data Source")
    data_source = st.radio(
        label="data_source",
        options=["CSV", "Parquet"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )

    data_path = CSV_PATH if data_source == "CSV" else PARQUET_PATH

    if not data_path.exists():
        st.error(f"File not found: `{data_path}`\n\nRun the pipeline first to generate the output.")
        st.stop()

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
_file_size = data_path.stat().st_size
_size_str  = f"{_file_size / 1e9:.1f} GB"
with st.spinner(f"Sampling {SAMPLE_ROWS:,} rows from {_size_str} {data_source} file…"):
    df_full = load_csv(CSV_PATH, SAMPLE_ROWS) if data_source == "CSV" else load_parquet(PARQUET_PATH, SAMPLE_ROWS)

# ---------------------------------------------------------------------------
# Derive LGA centroids from data
# ---------------------------------------------------------------------------
@st.cache_data
def compute_lga_centroids(df: pd.DataFrame) -> pd.DataFrame:
    origin_c = (
        df.groupby("origin_lga_name")
        .agg(lat=("origin_latitude", "mean"), lon=("origin_longitude", "mean"))
        .reset_index()
        .rename(columns={"origin_lga_name": "lga_name"})
    )
    dest_c = (
        df.groupby("destination_lga_name")
        .agg(lat=("destination_latitude", "mean"), lon=("destination_longitude", "mean"))
        .reset_index()
        .rename(columns={"destination_lga_name": "lga_name"})
    )
    return (
        pd.concat([origin_c, dest_c])
        .groupby("lga_name")
        .agg(lat=("lat", "mean"), lon=("lon", "mean"))
        .reset_index()
    )


lga_centroids = compute_lga_centroids(df_full)

ALL_TOURISM_REGIONS = sorted(
    set(df_full["origin_visit_tourism_region"].dropna())
    | set(df_full["destination_visit_tourism_region"].dropna())
)
MIN_DATE = df_full["date"].min()
MAX_DATE = df_full["date"].max()

# ---------------------------------------------------------------------------
# Sidebar — Filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()

    st.markdown(
        """
        <div style="background:#e8f4f8;border-left:4px solid #1a7abf;
                    padding:10px 14px;border-radius:4px;margin-bottom:16px;">
            <span style="font-size:13px;color:#555;">State</span><br>
            <span style="font-size:18px;font-weight:700;color:#1a7abf;">Victoria</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### 📅 Date Range")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_start = st.date_input("From", value=MIN_DATE, min_value=MIN_DATE, max_value=MAX_DATE)
    with col_d2:
        date_end = st.date_input("To", value=MAX_DATE, min_value=MIN_DATE, max_value=MAX_DATE)

    if date_start > date_end:
        st.error("Start date must be ≤ end date.")
        st.stop()

    st.markdown("#### 🌏 Tourism Region")
    region_sel = st.multiselect(
        label="tourism_region",
        options=ALL_TOURISM_REGIONS,
        default=[],
        placeholder="All regions",
        label_visibility="collapsed",
    )

    st.markdown("#### 🔢 Min Trips per Corridor")
    min_trips = st.slider("min_trips", min_value=1, max_value=500, value=5, label_visibility="collapsed")

    st.markdown("#### 🗺️ Top N Corridors on Map")
    top_n_map = st.slider("top_n_map", min_value=5, max_value=100, value=30, label_visibility="collapsed")

    st.divider()
    if st.button("🔄 Reset Filters", use_container_width=True):
        st.rerun()

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
df = df_full.copy()
df = df[(df["date"] >= date_start) & (df["date"] <= date_end)]

if region_sel:
    df = df[
        df["origin_visit_tourism_region"].isin(region_sel)
        | df["destination_visit_tourism_region"].isin(region_sel)
    ]

# ---------------------------------------------------------------------------
# Temporal flag columns
# ---------------------------------------------------------------------------
_WEEKDAYS    = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
_WEEKENDS    = {"Saturday", "Sunday"}
_AM_PEAK_HRS = {7, 8, 9}
_PM_PEAK_HRS = {16, 17, 18}

_wd = df["day_of_week"].isin(_WEEKDAYS)
_we = df["day_of_week"].isin(_WEEKENDS)
_am = df["hour_of_day"].isin(_AM_PEAK_HRS)
_pm = df["hour_of_day"].isin(_PM_PEAK_HRS)

df = df.copy()
df["_is_weekday"]  = _wd.astype(float)
df["_is_weekend"]  = _we.astype(float)
df["_is_wkday_am"] = (_wd & _am).astype(float)
df["_is_wkday_pm"] = (_wd & _pm).astype(float)
df["_is_wkend_am"] = (_we & _am).astype(float)
df["_is_wkend_pm"] = (_we & _pm).astype(float)

# ---------------------------------------------------------------------------
# Build corridor summary
# ---------------------------------------------------------------------------
corridor_df = (
    df.groupby(["origin_lga_name", "destination_lga_name"])
    .agg(
        n_trips=("device_id", "count"),
        n_devices=("device_id", "nunique"),
        avg_distance_km=("distance_km", "mean"),
        origin_tourism_region=("origin_visit_tourism_region", "first"),
        dest_tourism_region=("destination_visit_tourism_region", "first"),
        pct_weekday=("_is_weekday", "mean"),
        pct_weekend=("_is_weekend", "mean"),
        pct_weekday_am_peak=("_is_wkday_am", "mean"),
        pct_weekday_pm_peak=("_is_wkday_pm", "mean"),
        pct_weekend_am_peak=("_is_wkend_am", "mean"),
        pct_weekend_pm_peak=("_is_wkend_pm", "mean"),
    )
    .reset_index()
    .sort_values("n_trips", ascending=False)
)

for _c in ["pct_weekday", "pct_weekend", "pct_weekday_am_peak",
           "pct_weekday_pm_peak", "pct_weekend_am_peak", "pct_weekend_pm_peak"]:
    corridor_df[_c] = (corridor_df[_c] * 100).round(1)

corridor_df = corridor_df[corridor_df["n_trips"] >= min_trips].copy()

corridor_df = corridor_df.merge(
    lga_centroids.rename(columns={"lga_name": "origin_lga_name", "lat": "origin_lat", "lon": "origin_lon"}),
    on="origin_lga_name", how="left",
).merge(
    lga_centroids.rename(columns={"lga_name": "destination_lga_name", "lat": "dest_lat", "lon": "dest_lon"}),
    on="destination_lga_name", how="left",
)

corridor_df["corridor"] = corridor_df["origin_lga_name"] + "  →  " + corridor_df["destination_lga_name"]
corridor_df["avg_distance_km"] = corridor_df["avg_distance_km"].round(1)
corridor_df["rank"] = range(1, len(corridor_df) + 1)

# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------
if len(df) == 0 or len(corridor_df) == 0:
    st.title("🛣️ Localis — Live Corridor Statistics")
    st.warning("No trips match the selected filters. Adjust the sidebar filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.markdown("# 🛣️ Localis — Live Corridor Statistics")
st.caption(
    f"Source: **{data_source}** · {len(df_full):,} total trips · "
    f"Filtered to {len(df):,} trips across {len(corridor_df):,} corridors · "
    f"{date_start} → {date_end}"
)
st.warning(
    f"**Sample mode** — showing first {SAMPLE_ROWS:,} rows from a {_size_str} file. "
    "All charts and corridor statistics reflect this sample only."
)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Trips",        f"{len(df):,}")
k2.metric("Unique Devices",     f"{df['device_id'].nunique():,}")
k3.metric("Active Corridors",   f"{len(corridor_df):,}")
k4.metric("Avg Distance (km)",  f"{df['distance_km'].mean():.1f}")
k5.metric("Top Corridor Trips", f"{corridor_df['n_trips'].iloc[0]:,}")

st.divider()

# ---------------------------------------------------------------------------
# OD Flow Map
# ---------------------------------------------------------------------------
chart_header(f"🗺️ OD Flow Map — Top {top_n_map} Corridors", INFO_MAP_P4, h3=True)

map_df = (
    corridor_df
    .dropna(subset=["origin_lat", "origin_lon", "dest_lat", "dest_lon"])
    .head(top_n_map)
    .copy()
)

if len(map_df) > 0:
    max_tc = map_df["n_trips"].max()
    min_tc = map_df["n_trips"].min()
    range_tc = max(max_tc - min_tc, 1)

    fig_map = go.Figure()

    for _, row in map_df.iterrows():
        norm = (row["n_trips"] - min_tc) / range_tc
        fig_map.add_trace(go.Scattermapbox(
            lat=[row["origin_lat"], row["dest_lat"], None],
            lon=[row["origin_lon"], row["dest_lon"], None],
            mode="lines",
            line=dict(width=1 + norm * 7, color=f"rgba(26,122,191,{0.35 + norm * 0.55:.2f})"),
            hoverinfo="skip",
            showlegend=False,
        ))

    fig_map.add_trace(go.Scattermapbox(
        lat=map_df["origin_lat"].tolist(),
        lon=map_df["origin_lon"].tolist(),
        mode="markers",
        marker=dict(size=8, color="#1a7abf", opacity=0.9),
        text=map_df["origin_lga_name"],
        hovertemplate="<b>Origin:</b> %{text}<extra></extra>",
        name="Origin LGA",
    ))

    fig_map.add_trace(go.Scattermapbox(
        lat=map_df["dest_lat"].tolist(),
        lon=map_df["dest_lon"].tolist(),
        mode="markers",
        marker=dict(size=8, color="#e85d04", opacity=0.9),
        text=map_df["destination_lga_name"],
        hovertemplate="<b>Destination:</b> %{text}<extra></extra>",
        name="Destination LGA",
    ))

    map_df["mid_lat"] = (map_df["origin_lat"] + map_df["dest_lat"]) / 2
    map_df["mid_lon"] = (map_df["origin_lon"] + map_df["dest_lon"]) / 2
    fig_map.add_trace(go.Scattermapbox(
        lat=map_df["mid_lat"].tolist(),
        lon=map_df["mid_lon"].tolist(),
        mode="markers",
        marker=dict(size=14, color="rgba(0,0,0,0)"),
        text=map_df["corridor"].tolist(),
        customdata=map_df[["n_trips", "avg_distance_km"]].values,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Trips: %{customdata[0]:,}<br>"
            "Avg distance: %{customdata[1]:.1f} km<extra></extra>"
        ),
        showlegend=False,
    ))

    center_lat = (map_df["origin_lat"].mean() + map_df["dest_lat"].mean()) / 2
    center_lon = (map_df["origin_lon"].mean() + map_df["dest_lon"].mean()) / 2

    fig_map.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=5.5),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("No corridors with valid centroid coordinates to display.")

st.divider()

# ---------------------------------------------------------------------------
# Row 2: Top 20 Corridors + Daily Trend + Weekly Pattern
# ---------------------------------------------------------------------------
col_bar, col_right = st.columns([3, 2])

with col_bar:
    chart_header("Top 20 Corridors by Trip Count", INFO_TOP20, h3=True)
    top20 = corridor_df.head(20).sort_values("n_trips")
    fig_bar = px.bar(
        top20,
        x="n_trips", y="corridor", orientation="h", text="n_trips",
        color="avg_distance_km", color_continuous_scale="Blues",
        labels={"n_trips": "Trips", "corridor": "", "avg_distance_km": "Avg km"},
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        coloraxis_colorbar=dict(title="Avg km", thickness=12, len=0.6),
        margin=dict(l=0, r=30, t=10, b=10),
        height=500,
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_right:
    chart_header("Daily Trip Volume", INFO_DAILY, h3=True)
    daily = df.groupby("date").size().reset_index(name="trips")
    daily["date"] = pd.to_datetime(daily["date"])
    fig_trend = px.line(
        daily, x="date", y="trips",
        labels={"date": "", "trips": "Trips"},
        color_discrete_sequence=["#1a7abf"],
    )
    fig_trend.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=230)
    st.plotly_chart(fig_trend, use_container_width=True)

    chart_header("Trips by Day of Week", INFO_DOW_P4, h3=True)
    dow = (
        df.groupby("day_of_week").size()
        .reindex([d for d in DOW_ORDER if d in df["day_of_week"].unique()])
        .reset_index(name="trips")
    )
    fig_dow = px.bar(
        dow, x="day_of_week", y="trips",
        labels={"day_of_week": "", "trips": "Trips"},
        color_discrete_sequence=["#1a7abf"],
    )
    fig_dow.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=230)
    st.plotly_chart(fig_dow, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Row 3: DoW × Hour Heatmap + Distance by Tourism Region
# ---------------------------------------------------------------------------
col_heat, col_region = st.columns([3, 2])

with col_heat:
    chart_header("Trip Intensity — Day of Week × Hour of Day", INFO_HEAT, h3=True)
    dow_hour = df.groupby(["day_of_week", "hour_of_day"]).size().reset_index(name="trips")
    dow_hour["day_of_week"] = pd.Categorical(
        dow_hour["day_of_week"], categories=DOW_ORDER, ordered=True
    )
    pivot_heat = (
        dow_hour.sort_values("day_of_week")
        .pivot(index="day_of_week", columns="hour_of_day", values="trips")
        .fillna(0)
    )
    fig_heat = px.imshow(
        pivot_heat,
        labels=dict(x="Hour of Day", y="", color="Trips"),
        color_continuous_scale="Blues",
        aspect="auto",
    )
    fig_heat.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=280)
    st.plotly_chart(fig_heat, use_container_width=True)

with col_region:
    chart_header("Avg Distance by Origin Tourism Region", INFO_REGION_DIST, h3=True)
    region_dist = (
        df.groupby("origin_visit_tourism_region")
        .agg(avg_km=("distance_km", "mean"), trips=("device_id", "count"))
        .reset_index()
        .dropna(subset=["origin_visit_tourism_region"])
        .sort_values("avg_km", ascending=True)
    )
    fig_region = px.bar(
        region_dist,
        x="avg_km", y="origin_visit_tourism_region", orientation="h",
        text=region_dist["avg_km"].round(0).astype(int),
        color="trips", color_continuous_scale="Greens",
        labels={"avg_km": "Avg Distance (km)", "origin_visit_tourism_region": "", "trips": "Trips"},
    )
    fig_region.update_traces(textposition="outside")
    fig_region.update_layout(
        margin=dict(l=0, r=30, t=10, b=10),
        height=280,
        coloraxis_colorbar=dict(title="Trips", thickness=12, len=0.6),
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_region, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# OD Matrix — top 10 × top 10
# ---------------------------------------------------------------------------
chart_header("OD Matrix — Top 10 Origins × Top 10 Destinations", INFO_MATRIX_P4, h3=True)

top10_o = corridor_df.groupby("origin_lga_name")["n_trips"].sum().nlargest(10).index.tolist()
top10_d = corridor_df.groupby("destination_lga_name")["n_trips"].sum().nlargest(10).index.tolist()

matrix_sub = corridor_df[
    corridor_df["origin_lga_name"].isin(top10_o)
    & corridor_df["destination_lga_name"].isin(top10_d)
]

if len(matrix_sub) > 0:
    pivot_matrix = (
        matrix_sub.pivot_table(
            index="origin_lga_name", columns="destination_lga_name",
            values="n_trips", fill_value=0,
        )
        .reindex(index=top10_o, columns=top10_d, fill_value=0)
    )
    fig_matrix = px.imshow(
        pivot_matrix,
        labels=dict(x="Destination LGA", y="Origin LGA", color="Trips"),
        color_continuous_scale="Blues",
        text_auto=True,
        aspect="auto",
    )
    fig_matrix.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        height=400,
        xaxis=dict(tickangle=-35, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10)),
    )
    st.plotly_chart(fig_matrix, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Peak Hour Share — top 15 corridors
# ---------------------------------------------------------------------------
chart_header("Peak Hour Share — Top 15 Corridors", INFO_PEAK, h3=True)

top15 = corridor_df.head(15).sort_values("n_trips")

col_wkday, col_wkend = st.columns(2)

with col_wkday:
    st.markdown("**Weekday Peaks**")
    wkday_df = top15[["corridor", "pct_weekday_am_peak", "pct_weekday_pm_peak"]].melt(
        id_vars="corridor", var_name="Period", value_name="% of Trips"
    )
    wkday_df["Period"] = wkday_df["Period"].map({
        "pct_weekday_am_peak": "AM Peak (07–09)",
        "pct_weekday_pm_peak": "PM Peak (16–18)",
    })
    fig_wkday = px.bar(
        wkday_df, x="% of Trips", y="corridor", color="Period",
        orientation="h", barmode="group",
        color_discrete_map={"AM Peak (07–09)": "#1a7abf", "PM Peak (16–18)": "#4fb3e8"},
        labels={"corridor": "", "% of Trips": "% of Trips"},
    )
    fig_wkday.update_layout(
        margin=dict(l=0, r=10, t=10, b=10), height=480,
        yaxis=dict(tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    st.plotly_chart(fig_wkday, use_container_width=True)

with col_wkend:
    st.markdown("**Weekend Peaks**")
    wkend_df = top15[["corridor", "pct_weekend_am_peak", "pct_weekend_pm_peak"]].melt(
        id_vars="corridor", var_name="Period", value_name="% of Trips"
    )
    wkend_df["Period"] = wkend_df["Period"].map({
        "pct_weekend_am_peak": "AM Peak (07–09)",
        "pct_weekend_pm_peak": "PM Peak (16–18)",
    })
    fig_wkend = px.bar(
        wkend_df, x="% of Trips", y="corridor", color="Period",
        orientation="h", barmode="group",
        color_discrete_map={"AM Peak (07–09)": "#e85d04", "PM Peak (16–18)": "#f4a261"},
        labels={"corridor": "", "% of Trips": "% of Trips"},
    )
    fig_wkend.update_layout(
        margin=dict(l=0, r=10, t=10, b=10), height=480,
        yaxis=dict(tickfont=dict(size=9)),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    st.plotly_chart(fig_wkend, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Weekday vs Weekend split — top 15 corridors
# ---------------------------------------------------------------------------
chart_header("Weekday vs Weekend Split — Top 15 Corridors", INFO_SPLIT, h3=True)

split_df = corridor_df.head(15)[["corridor", "pct_weekday", "pct_weekend"]].melt(
    id_vars="corridor", var_name="Type", value_name="% of Trips"
)
split_df["Type"] = split_df["Type"].map({"pct_weekday": "Weekday", "pct_weekend": "Weekend"})

fig_split = px.bar(
    split_df, x="% of Trips", y="corridor", color="Type",
    orientation="h", barmode="stack",
    color_discrete_map={"Weekday": "#1a7abf", "Weekend": "#e85d04"},
    labels={"corridor": "", "% of Trips": "% of Corridor Trips"},
)
fig_split.update_layout(
    margin=dict(l=0, r=20, t=10, b=10),
    height=420,
    yaxis=dict(tickfont=dict(size=10)),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
)
st.plotly_chart(fig_split, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Corridor Summary Table
# ---------------------------------------------------------------------------
total_trips_count = corridor_df["n_trips"].sum()
TABLE_PREVIEW_LIMIT = 5_000

st.markdown(
    f"### Corridor Summary Table &nbsp;"
    f"<span style='font-size:14px;color:#888;'>"
    f"{len(corridor_df):,} corridors · min {min_trips} trips · {date_start} → {date_end}"
    + (f" &nbsp;·&nbsp; showing first {TABLE_PREVIEW_LIMIT:,}" if len(corridor_df) > TABLE_PREVIEW_LIMIT else "")
    + "</span>",
    unsafe_allow_html=True,
)

table_df = corridor_df[[
    "rank",
    "origin_lga_name", "origin_tourism_region", "origin_lat", "origin_lon",
    "destination_lga_name", "dest_tourism_region", "dest_lat", "dest_lon",
    "n_trips", "n_devices", "avg_distance_km",
    "pct_weekday", "pct_weekday_am_peak", "pct_weekday_pm_peak",
    "pct_weekend", "pct_weekend_am_peak", "pct_weekend_pm_peak",
]].rename(columns={
    "rank": "Rank",
    "origin_lga_name": "Origin LGA", "origin_tourism_region": "Origin Tourism Region",
    "origin_lat": "Origin Centroid Lat", "origin_lon": "Origin Centroid Lon",
    "destination_lga_name": "Dest LGA", "dest_tourism_region": "Dest Tourism Region",
    "dest_lat": "Dest Centroid Lat", "dest_lon": "Dest Centroid Lon",
    "n_trips": "Trips", "n_devices": "Devices", "avg_distance_km": "Avg Dist (km)",
    "pct_weekday": "% Weekday", "pct_weekday_am_peak": "% Wkday AM Peak",
    "pct_weekday_pm_peak": "% Wkday PM Peak", "pct_weekend": "% Weekend",
    "pct_weekend_am_peak": "% Wkend AM Peak", "pct_weekend_pm_peak": "% Wkend PM Peak",
}).copy()

table_df["% of Total"] = (corridor_df["n_trips"].values / total_trips_count * 100).round(2)

st.dataframe(
    table_df.head(TABLE_PREVIEW_LIMIT),
    use_container_width=True,
    height=520,
    hide_index=True,
    column_config={
        "Rank":                 st.column_config.NumberColumn("Rank",              format="%d"),
        "Trips":                st.column_config.NumberColumn("Trips",             format="%d"),
        "Devices":              st.column_config.NumberColumn("Devices",           format="%d"),
        "Avg Dist (km)":        st.column_config.NumberColumn("Avg Dist (km)",     format="%.1f km"),
        "Origin Centroid Lat":  st.column_config.NumberColumn("Origin Lat",        format="%.5f°"),
        "Origin Centroid Lon":  st.column_config.NumberColumn("Origin Lon",        format="%.5f°"),
        "Dest Centroid Lat":    st.column_config.NumberColumn("Dest Lat",          format="%.5f°"),
        "Dest Centroid Lon":    st.column_config.NumberColumn("Dest Lon",          format="%.5f°"),
        "% of Total":           st.column_config.NumberColumn("% of Total",        format="%.2f%%"),
        "% Weekday":            st.column_config.NumberColumn("% Weekday",         format="%.1f%%"),
        "% Wkday AM Peak":      st.column_config.NumberColumn("% Wkday AM Peak",   format="%.1f%%"),
        "% Wkday PM Peak":      st.column_config.NumberColumn("% Wkday PM Peak",   format="%.1f%%"),
        "% Weekend":            st.column_config.NumberColumn("% Weekend",         format="%.1f%%"),
        "% Wkend AM Peak":      st.column_config.NumberColumn("% Wkend AM Peak",   format="%.1f%%"),
        "% Wkend PM Peak":      st.column_config.NumberColumn("% Wkend PM Peak",   format="%.1f%%"),
    },
)

st.caption("⚡ This download reflects the sample. Use **Full Export** below for complete data.")
csv_bytes = io.BytesIO()
table_df.to_csv(csv_bytes, index=False)
st.download_button(
    label=f"⬇️ Download sample corridor summary  —  od_corridors_{date_start}_{date_end}.csv",
    data=csv_bytes.getvalue(),
    file_name=f"od_corridors_{date_start}_{date_end}.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# Full export — recomputes corridors from complete file
# ---------------------------------------------------------------------------
st.divider()
st.markdown("#### 💾 Export Full Corridor Summary (from complete dataset)")
st.caption(
    f"Reads the complete {_size_str} file, applies your current filters, "
    "recomputes all corridor statistics, and saves to the server."
)

for _k in ("od_export_path", "od_export_rows", "od_export_bytes", "od_export_name"):
    if _k not in st.session_state:
        st.session_state[_k] = None

if st.button("⚙️ Prepare full corridor export", use_container_width=True):
    with st.spinner(f"Reading full {data_source} file and computing corridors — may take a few minutes…"):
        _dfe = (
            load_csv(CSV_PATH, nrows=None)
            if data_source == "CSV"
            else load_parquet(PARQUET_PATH, nrows=None)
        )
        _dfe = _dfe[(_dfe["date"] >= date_start) & (_dfe["date"] <= date_end)]
        if region_sel:
            _dfe = _dfe[
                _dfe["origin_visit_tourism_region"].isin(region_sel)
                | _dfe["destination_visit_tourism_region"].isin(region_sel)
            ]
        _dfe = _dfe.copy()
        _wd_e = _dfe["day_of_week"].isin(_WEEKDAYS)
        _we_e = _dfe["day_of_week"].isin(_WEEKENDS)
        _am_e = _dfe["hour_of_day"].isin(_AM_PEAK_HRS)
        _pm_e = _dfe["hour_of_day"].isin(_PM_PEAK_HRS)
        _dfe["_is_weekday"]  = _wd_e.astype(float)
        _dfe["_is_weekend"]  = _we_e.astype(float)
        _dfe["_is_wkday_am"] = (_wd_e & _am_e).astype(float)
        _dfe["_is_wkday_pm"] = (_wd_e & _pm_e).astype(float)
        _dfe["_is_wkend_am"] = (_we_e & _am_e).astype(float)
        _dfe["_is_wkend_pm"] = (_we_e & _pm_e).astype(float)
        _corr_e = (
            _dfe.groupby(["origin_lga_name", "destination_lga_name"])
            .agg(
                n_trips=("device_id", "count"),
                n_devices=("device_id", "nunique"),
                avg_distance_km=("distance_km", "mean"),
                origin_tourism_region=("origin_visit_tourism_region", "first"),
                dest_tourism_region=("destination_visit_tourism_region", "first"),
                pct_weekday=("_is_weekday", "mean"),
                pct_weekend=("_is_weekend", "mean"),
                pct_weekday_am_peak=("_is_wkday_am", "mean"),
                pct_weekday_pm_peak=("_is_wkday_pm", "mean"),
                pct_weekend_am_peak=("_is_wkend_am", "mean"),
                pct_weekend_pm_peak=("_is_wkend_pm", "mean"),
            )
            .reset_index()
            .sort_values("n_trips", ascending=False)
        )
        for _c in ["pct_weekday", "pct_weekend", "pct_weekday_am_peak",
                   "pct_weekday_pm_peak", "pct_weekend_am_peak", "pct_weekend_pm_peak"]:
            _corr_e[_c] = (_corr_e[_c] * 100).round(1)
        _corr_e = _corr_e[_corr_e["n_trips"] >= min_trips].copy()
        _corr_e = _corr_e.merge(
            lga_centroids.rename(columns={"lga_name": "origin_lga_name", "lat": "origin_lat", "lon": "origin_lon"}),
            on="origin_lga_name", how="left",
        ).merge(
            lga_centroids.rename(columns={"lga_name": "destination_lga_name", "lat": "dest_lat", "lon": "dest_lon"}),
            on="destination_lga_name", how="left",
        )
        _corr_e["avg_distance_km"] = _corr_e["avg_distance_km"].round(1)
        _corr_e["rank"] = range(1, len(_corr_e) + 1)
        _total_e = _corr_e["n_trips"].sum()
        _tbl_e = _corr_e[[
            "rank",
            "origin_lga_name", "origin_tourism_region", "origin_lat", "origin_lon",
            "destination_lga_name", "dest_tourism_region", "dest_lat", "dest_lon",
            "n_trips", "n_devices", "avg_distance_km",
            "pct_weekday", "pct_weekday_am_peak", "pct_weekday_pm_peak",
            "pct_weekend", "pct_weekend_am_peak", "pct_weekend_pm_peak",
        ]].rename(columns={
            "rank": "Rank",
            "origin_lga_name": "Origin LGA", "origin_tourism_region": "Origin Tourism Region",
            "origin_lat": "Origin Centroid Lat", "origin_lon": "Origin Centroid Lon",
            "destination_lga_name": "Dest LGA", "dest_tourism_region": "Dest Tourism Region",
            "dest_lat": "Dest Centroid Lat", "dest_lon": "Dest Centroid Lon",
            "n_trips": "Trips", "n_devices": "Devices", "avg_distance_km": "Avg Dist (km)",
            "pct_weekday": "% Weekday", "pct_weekday_am_peak": "% Wkday AM Peak",
            "pct_weekday_pm_peak": "% Wkday PM Peak", "pct_weekend": "% Weekend",
            "pct_weekend_am_peak": "% Wkend AM Peak", "pct_weekend_pm_peak": "% Wkend PM Peak",
        }).copy()
        _tbl_e["% of Total"] = (_corr_e["n_trips"].values / _total_e * 100).round(2)
        _od_export_path = Path(tempfile.gettempdir()) / f"od_corridors_full_{date_start}_{date_end}.csv"
        _tbl_e.to_csv(_od_export_path, index=False)
        _od_exp_size = _od_export_path.stat().st_size
        _od_exp_name = f"od_corridors_full_{date_start}_{date_end}.csv"
        st.session_state.od_export_path  = str(_od_export_path)
        st.session_state.od_export_rows  = len(_tbl_e)
        st.session_state.od_export_name  = _od_exp_name
        st.session_state.od_export_bytes = (
            _od_export_path.read_bytes() if _od_exp_size < DOWNLOAD_SIZE_THRESHOLD else None
        )

if st.session_state.od_export_path:
    st.success(f"✅ {st.session_state.od_export_rows:,} corridors saved → `{st.session_state.od_export_path}`")
    if st.session_state.od_export_bytes:
        st.download_button(
            label=f"⬇️ Download now  —  `{st.session_state.od_export_name}`",
            data=st.session_state.od_export_bytes,
            file_name=st.session_state.od_export_name,
            mime="text/csv",
        )
    else:
        _od_mb = Path(st.session_state.od_export_path).stat().st_size / 1e6
        st.info(
            f"File is {_od_mb:.0f} MB — too large for the browser.\n\n"
            f"Copy from server:  `scp ubuntu@<ip>:{st.session_state.od_export_path} .`"
        )
