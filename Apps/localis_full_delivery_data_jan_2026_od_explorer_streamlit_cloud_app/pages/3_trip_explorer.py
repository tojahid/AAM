# =============================================================================
# 3_trip_explorer.py — Localis Trip-Level Explorer (Streamlit page)
#
# Self-contained page to explore the trip-level pipeline output.
# Adapted from app_trip_explorer_trip_level.py — path corrected for new depth.
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
from utils import chart_header, ensure_gdrive_file

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Paths / sampling config
# ---------------------------------------------------------------------------
APP_DIR      = Path(__file__).parent
OUTPUT_DIR   = APP_DIR.parent / "output"
CSV_PATH     = OUTPUT_DIR / "trips_jan_2026.csv"
PARQUET_PATH = OUTPUT_DIR / "trips.parquet"
EXPORT_PATH  = Path(tempfile.gettempdir()) / "filtered_export.csv"

# Google Drive file ID for trips_20GB.csv
# Share the file: Drive → right-click → Share → Anyone with link (Viewer)
# Copy the ID from: https://drive.google.com/file/d/FILE_ID_HERE/view
GDRIVE_CSV_FILE_ID = "1RsGks2qXD_pYPikChEmEalq42kvUMTV3"

LARGE_FILE_THRESHOLD    = 1000 * 1024 * 1024   # 500 MB
SAMPLE_ROWS             = 500_000
DOWNLOAD_SIZE_THRESHOLD = 150 * 1024 * 1024   # 150 MB

INFO_TOP15 = (
    "Top 15 origin–destination LGA pairs ranked by number of trip records in the current "
    "sample. Colour shade indicates average trip distance (darker = longer). "
    "**Use this** to quickly see which OD pairs dominate demand within your filter selection. "
    "Apply Origin LGA or Destination LGA filters in the sidebar to focus on a specific market."
)
INFO_DIST = (
    "Histogram of trip distances (km) across all filtered trips in the sample. "
    "Trips are pre-filtered to ≥70 km Haversine at pipeline level. "
    "A peak in a distance band shows where most demand is concentrated — "
    "useful for sizing aircraft range requirements or route network planning."
)
INFO_DOW_P3 = (
    "Total trip count per day of week from the filtered sample. "
    "Compare weekday (Mon–Fri) vs weekend (Sat–Sun) volumes to assess the "
    "commuter vs leisure travel mix for the selected corridors and date range."
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
# Sidebar — Part 1: Data source only
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📋 Browse Raw Trip Records")
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

    st.divider()

# ---------------------------------------------------------------------------
# Resolve data path — download from Google Drive for CSV if not present locally
# ---------------------------------------------------------------------------
if data_source == "CSV" and not data_path.exists():
    if not GDRIVE_CSV_FILE_ID:
        st.error(
            "trips_20GB.csv not found in `output/` and no Google Drive file ID is set.\n\n"
            "Set `GDRIVE_CSV_FILE_ID` at the top of this file."
        )
        st.stop()
    resolved_path = ensure_gdrive_file("trips_20GB.csv", GDRIVE_CSV_FILE_ID, OUTPUT_DIR)
elif data_source == "Parquet" and not data_path.exists():
    st.error(f"File not found: `{data_path}`\n\nAdd trips.parquet to the `output/` folder.")
    st.stop()
else:
    resolved_path = data_path

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
_file_size = resolved_path.stat().st_size
_size_str  = f"{_file_size / 1e9:.1f} GB"
with st.spinner(f"Sampling {SAMPLE_ROWS:,} rows from {_size_str} {data_source} file…"):
    df_full = load_csv(resolved_path, SAMPLE_ROWS) if data_source == "CSV" else load_parquet(resolved_path, SAMPLE_ROWS)

ALL_LGAS = sorted(set(df_full["origin_lga_name"].tolist()) | set(df_full["destination_lga_name"].tolist()))
MIN_DATE = df_full["date"].min()
MAX_DATE = df_full["date"].max()

# ---------------------------------------------------------------------------
# Sidebar — Part 2: Filters
# ---------------------------------------------------------------------------
with st.sidebar:
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

    st.markdown("#### 📍 Origin LGA")
    origin_sel = st.multiselect(
        label="origin_lga",
        options=ALL_LGAS,
        default=[],
        placeholder="All LGAs",
        label_visibility="collapsed",
    )

    st.markdown("#### 🏁 Destination LGA")
    dest_sel = st.multiselect(
        label="dest_lga",
        options=ALL_LGAS,
        default=[],
        placeholder="All LGAs",
        label_visibility="collapsed",
    )

    st.markdown("#### 📅 Date Range")
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        date_start = st.date_input("From", value=MIN_DATE, min_value=MIN_DATE, max_value=MAX_DATE, label_visibility="visible")
    with col_d2:
        date_end   = st.date_input("To",   value=MAX_DATE, min_value=MIN_DATE, max_value=MAX_DATE, label_visibility="visible")

    if date_start > date_end:
        st.error("Start date must be ≤ end date.")
        st.stop()

    st.divider()
    if st.button("🔄 Reset Filters", use_container_width=True):
        st.rerun()

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------
df = df_full.copy()

if origin_sel:
    df = df[df["origin_lga_name"].isin(origin_sel)]
if dest_sel:
    df = df[df["destination_lga_name"].isin(dest_sel)]
df = df[(df["date"] >= date_start) & (df["date"] <= date_end)]

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------
st.markdown("# 📋 Localis — Browse Raw Trip Records")
st.caption(
    f"Source: **{data_source}** · {len(df_full):,} total trips · "
    f"Date range in data: {MIN_DATE} → {MAX_DATE}"
)
st.warning(
    f"**Sample mode** — showing first {SAMPLE_ROWS:,} rows from a {_size_str} file. "
    "Charts reflect this sample. Use **Export Full Data** at the bottom to download the complete dataset."
)

# ---------------------------------------------------------------------------
# KPI metrics row
# ---------------------------------------------------------------------------
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Total Trips",       f"{len(df):,}")
k2.metric("Unique Devices",    f"{df['device_id'].nunique():,}")
k3.metric("Unique Corridors",
           f"{df[['origin_lga_name','destination_lga_name']].drop_duplicates().shape[0]:,}")
k4.metric("Avg Distance (km)", f"{df['distance_km'].mean():.1f}" if len(df) else "—")
k5.metric("Max Distance (km)", f"{df['distance_km'].max():.1f}"  if len(df) else "—")

st.divider()

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
if len(df) == 0:
    st.warning("No trips match the selected filters. Adjust the filters in the sidebar.")
    st.stop()

chart_col, dist_col = st.columns([3, 2])

with chart_col:
    chart_header("Top 15 Corridors by Trip Count", INFO_TOP15, h3=True)
    top = (
        df.groupby(["origin_lga_name", "destination_lga_name"])
        .agg(trips=("device_id", "count"), avg_dist=("distance_km", "mean"))
        .reset_index()
        .sort_values("trips", ascending=False)
        .head(15)
        .copy()
    )
    top["corridor"] = top["origin_lga_name"] + "  →  " + top["destination_lga_name"]

    fig_bar = px.bar(
        top.sort_values("trips"),
        x="trips",
        y="corridor",
        orientation="h",
        text="trips",
        color="avg_dist",
        color_continuous_scale="Blues",
        labels={"trips": "Trip Count", "corridor": "", "avg_dist": "Avg Dist (km)"},
    )
    fig_bar.update_traces(textposition="outside")
    fig_bar.update_layout(
        coloraxis_colorbar=dict(title="Avg km", thickness=12, len=0.6),
        margin=dict(l=0, r=20, t=10, b=10),
        height=420,
        yaxis=dict(tickfont=dict(size=11)),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with dist_col:
    chart_header("Distance Distribution", INFO_DIST, h3=True)
    fig_hist = px.histogram(
        df,
        x="distance_km",
        nbins=30,
        labels={"distance_km": "Distance (km)", "count": "Trips"},
        color_discrete_sequence=["#1a7abf"],
    )
    fig_hist.update_layout(
        margin=dict(l=0, r=0, t=10, b=10),
        height=200,
        bargap=0.05,
        yaxis_title="Trips",
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    chart_header("Trips by Day of Week", INFO_DOW_P3, h3=True)
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow = (
        df.groupby("day_of_week")
        .size()
        .reindex([d for d in dow_order if d in df["day_of_week"].unique()])
        .reset_index(name="trips")
    )
    fig_dow = px.bar(
        dow,
        x="day_of_week",
        y="trips",
        labels={"day_of_week": "", "trips": "Trips"},
        color_discrete_sequence=["#1a7abf"],
    )
    fig_dow.update_layout(margin=dict(l=0, r=0, t=10, b=10), height=185)
    st.plotly_chart(fig_dow, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Full data table
# ---------------------------------------------------------------------------
TABLE_PREVIEW_LIMIT = 5_000

st.markdown(
    f"### Trip Records &nbsp;"
    f"<span style='font-size:14px;color:#888;'>"
    f"{len(df):,} rows · 18 columns"
    + (f" &nbsp;·&nbsp; showing first {TABLE_PREVIEW_LIMIT:,}" if len(df) > TABLE_PREVIEW_LIMIT else "")
    + "</span>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;font-size:13px;">
        <span style="background:#dbeafe;color:#1e40af;padding:3px 10px;border-radius:12px;font-weight:600;">
            🔑 Identifiers &nbsp;·&nbsp; device_id &nbsp;·&nbsp; trip_seq_id
        </span>
        <span style="background:#fef3c7;color:#92400e;padding:3px 10px;border-radius:12px;font-weight:600;">
            🕐 Time &nbsp;·&nbsp; date &nbsp;·&nbsp; day_of_week &nbsp;·&nbsp; hour_of_day
        </span>
        <span style="background:#dcfce7;color:#166534;padding:3px 10px;border-radius:12px;font-weight:600;">
            📍 Spatial &nbsp;·&nbsp; LGA &nbsp;·&nbsp; Lat/Lon &nbsp;·&nbsp; H3 &nbsp;·&nbsp; Tourism Region &nbsp;·&nbsp; Home
        </span>
        <span style="background:#fae8ff;color:#6b21a8;padding:3px 10px;border-radius:12px;font-weight:600;">
            📏 Distance (km)
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)

COLUMN_ORDER = [
    "device_id", "trip_seq_id",
    "date", "day_of_week", "hour_of_day",
    "origin_lga_name", "destination_lga_name",
    "origin_latitude", "origin_longitude",
    "destination_latitude", "destination_longitude",
    "origin_visit_h3_index", "destination_visit_h3_index", "home_h3_index",
    "origin_visit_tourism_region", "destination_visit_tourism_region", "home_tourism_region_name",
    "distance_km",
]

display_df = df[COLUMN_ORDER].copy()
display_df["distance_km"]            = display_df["distance_km"].round(2)
display_df["origin_latitude"]        = display_df["origin_latitude"].round(6)
display_df["origin_longitude"]       = display_df["origin_longitude"].round(6)
display_df["destination_latitude"]   = display_df["destination_latitude"].round(6)
display_df["destination_longitude"]  = display_df["destination_longitude"].round(6)

display_df = display_df.rename(columns={
    "device_id": "Device ID", "trip_seq_id": "Trip #",
    "date": "Date", "day_of_week": "Day of Week", "hour_of_day": "Hour",
    "origin_lga_name": "Origin LGA", "destination_lga_name": "Destination LGA",
    "origin_latitude": "Origin Lat", "origin_longitude": "Origin Lon",
    "destination_latitude": "Dest Lat", "destination_longitude": "Dest Lon",
    "origin_visit_h3_index": "Origin H3 Index", "destination_visit_h3_index": "Dest H3 Index",
    "home_h3_index": "Home H3 Index",
    "origin_visit_tourism_region": "Origin Tourism Region",
    "destination_visit_tourism_region": "Dest Tourism Region",
    "home_tourism_region_name": "Home Tourism Region",
    "distance_km": "Distance (km)",
})

st.dataframe(
    display_df.head(TABLE_PREVIEW_LIMIT),
    use_container_width=True,
    height=520,
    hide_index=True,
    column_config={
        "Device ID":   st.column_config.TextColumn("Device ID",   help="Unique device identifier"),
        "Trip #":      st.column_config.NumberColumn("Trip #",     help="Per-device trip sequence number", format="%d"),
        "Date":        st.column_config.DateColumn("Date",         help="Calendar date of trip origin"),
        "Day of Week": st.column_config.TextColumn("Day of Week",  help="Full day name of trip origin"),
        "Hour":        st.column_config.NumberColumn("Hour",       help="Hour of trip origin (0–23)", format="%d:00"),
        "Origin LGA":       st.column_config.TextColumn("Origin LGA",      help="LGA where the trip started"),
        "Destination LGA":  st.column_config.TextColumn("Destination LGA", help="LGA where the trip ended"),
        "Origin Lat":  st.column_config.NumberColumn("Origin Lat",  help="Latitude of origin visit",      format="%.6f°"),
        "Origin Lon":  st.column_config.NumberColumn("Origin Lon",  help="Longitude of origin visit",     format="%.6f°"),
        "Dest Lat":    st.column_config.NumberColumn("Dest Lat",    help="Latitude of destination visit",  format="%.6f°"),
        "Dest Lon":    st.column_config.NumberColumn("Dest Lon",    help="Longitude of destination visit", format="%.6f°"),
        "Origin H3 Index":  st.column_config.TextColumn("Origin H3 Index",  help="H3 spatial index of origin visit"),
        "Dest H3 Index":    st.column_config.TextColumn("Dest H3 Index",    help="H3 spatial index of destination visit"),
        "Home H3 Index":    st.column_config.TextColumn("Home H3 Index",    help="H3 spatial index of device home"),
        "Origin Tourism Region": st.column_config.TextColumn("Origin Tourism Region", help="Tourism region of origin LGA"),
        "Dest Tourism Region":   st.column_config.TextColumn("Dest Tourism Region",   help="Tourism region of destination LGA"),
        "Home Tourism Region":   st.column_config.TextColumn("Home Tourism Region",   help="Tourism region of device home"),
        "Distance (km)": st.column_config.NumberColumn("Distance (km)", help="Haversine distance between LGA centroids", format="%.2f km"),
    },
)

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def _slug(selected: list[str], label: str) -> str:
    if not selected:
        return label
    if len(selected) == 1:
        return selected[0].replace(" ", "_").replace("(", "").replace(")", "")
    return f"multi_{len(selected)}"

origin_slug = _slug(origin_sel, "all_origins")
dest_slug   = _slug(dest_sel,   "all_destinations")
csv_filename = f"od_{origin_slug}_{dest_slug}_trip_level.csv"

st.caption("⚡ This download reflects the sample. Use **Full Export** below for complete data.")
_sample_csv = io.BytesIO()
df[COLUMN_ORDER].to_csv(_sample_csv, index=False)
st.download_button(
    label=f"⬇️ Download sample trips  —  `{csv_filename}`",
    data=_sample_csv.getvalue(),
    file_name=csv_filename,
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# Export full filtered data
# ---------------------------------------------------------------------------
st.divider()
st.markdown("#### 💾 Export Full Filtered Data (from complete dataset)")
st.caption(
    f"Reads the complete {_size_str} file, applies your current filters, "
    "and saves to the server."
)

for _k in ("export_path", "export_rows", "export_csv_bytes", "export_csv_name"):
    if _k not in st.session_state:
        st.session_state[_k] = None

if st.button("⚙️ Prepare full export", use_container_width=True):
    with st.spinner(f"Reading full {data_source} file and applying filters — may take a few minutes…"):
        _df_full_exp = (
            load_csv(resolved_path, nrows=None)
            if data_source == "CSV"
            else load_parquet(resolved_path, nrows=None)
        )
        _df_exp = _df_full_exp.copy()
        if origin_sel:
            _df_exp = _df_exp[_df_exp["origin_lga_name"].isin(origin_sel)]
        if dest_sel:
            _df_exp = _df_exp[_df_exp["destination_lga_name"].isin(dest_sel)]
        _df_exp = _df_exp[(_df_exp["date"] >= date_start) & (_df_exp["date"] <= date_end)]
        _export_cols = [c for c in COLUMN_ORDER if c in _df_exp.columns]
        _df_exp[_export_cols].to_csv(EXPORT_PATH, index=False)
        _exp_size = EXPORT_PATH.stat().st_size
        st.session_state.export_path      = str(EXPORT_PATH)
        st.session_state.export_rows      = len(_df_exp)
        st.session_state.export_csv_name  = csv_filename
        st.session_state.export_csv_bytes = (
            EXPORT_PATH.read_bytes() if _exp_size < DOWNLOAD_SIZE_THRESHOLD else None
        )

if st.session_state.export_path:
    st.success(f"✅ {st.session_state.export_rows:,} rows saved → `{st.session_state.export_path}`")
    if st.session_state.export_csv_bytes:
        st.download_button(
            label=f"⬇️ Download now  —  `{st.session_state.export_csv_name}`",
            data=st.session_state.export_csv_bytes,
            file_name=st.session_state.export_csv_name,
            mime="text/csv",
        )
    else:
        _exp_mb = EXPORT_PATH.stat().st_size / 1e6
        st.info(
            f"File is {_exp_mb:.0f} MB — too large for the browser.\n\n"
            f"Copy from server:  `scp ubuntu@<ip>:{EXPORT_PATH} .`"
        )
