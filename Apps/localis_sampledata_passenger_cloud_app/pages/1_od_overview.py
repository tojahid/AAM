"""
1_od_overview.py — AAM OD Overview (Streamlit page)

Strategic overview: top-N corridors, arc flow map, heatmaps, temporal demand.
Adapted from app_topn_od_explorer.py — config dependency removed.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import inject_css, kpi_tile_html, to_csv_bytes, chart_header

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_OUTPUT_DIR  = Path(__file__).parent.parent / "output"
RANKED_CSV   = str(_OUTPUT_DIR / "ranked_corridors.csv")
TEMPORAL_CSV = str(_OUTPUT_DIR / "temporal_distribution_all.csv")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERIOD_PCT_COL = {
    "All":              None,
    "Weekday":          "pct_weekday",
    "Weekday AM Peak":  "pct_weekday_am_peak",
    "Weekday PM Peak":  "pct_weekday_pm_peak",
    "Weekend":          "pct_weekend",
    "Weekend AM Peak":  "pct_weekend_am_peak",
    "Weekend PM Peak":  "pct_weekend_pm_peak",
}

# Palette
C_NAVY   = "#1e3a5f"
C_BLUE   = "#3b82f6"
C_SKY    = "#93c5fd"
C_ORANGE = "#f97316"
C_GRID   = "#f1f5f9"
C_BORDER = "rgba(49,51,63,0.10)"

# Arc quartile styling  [color, line_width, opacity, legend_label]
ARC_BUCKETS = [
    (C_NAVY,    3.5, 0.90, "High volume"),
    ("#1d4ed8", 2.5, 0.72, "Medium-high"),
    (C_BLUE,    1.8, 0.55, "Medium-low"),
    (C_SKY,     1.2, 0.38, "Low volume"),
]

# ---------------------------------------------------------------------------
# Info text for chart popovers
# ---------------------------------------------------------------------------

INFO_ARC_MAP = (
    "Shows straight-line arcs between LGA centroids. Line thickness and colour "
    "reflect relative trip volume — darkest arcs are the top 25% of corridors by trips, "
    "lightest are the bottom 25%. **Use this** to identify dominant flow corridors across "
    "Victoria at a glance and spot geographic demand clusters."
)
INFO_BAR = (
    "Horizontal bar chart ranking OD corridors by effective trip count for the selected "
    "time period. **Blue bars** = weekday dominant (≥50% weekday trips); "
    "**orange bars** = weekend dominant. Hover a bar for average distance and "
    "day-type breakdown. Capped at 30 corridors for readability."
)
INFO_REGION_HEAT = (
    "Aggregates corridor trips by Victoria tourism region. Darker cells = more trips "
    "between those two regions. **Use this** to spot high-demand region pairs and "
    "cross-regional travel patterns without the detail of individual LGAs."
)
INFO_LGA_MATRIX = (
    "Fine-grained version of the region heatmap at LGA level. Each cell shows the total "
    "trips between a specific origin–destination LGA pair. **Tip:** use a small Top-N "
    "(e.g. 10–25) to keep the matrix readable; with all corridors the labels will overlap."
)
INFO_TEMPORAL = (
    "Aggregated trip count by hour of day across all selected corridors. "
    "Shaded bands mark **AM peak (07–09)** and **PM peak (16–18)**. "
    "Switch the day-type filter between Weekday / Weekend to compare travel rhythms. "
    "Useful for sizing infrastructure by time-of-day demand."
)
INFO_INTENSITY = (
    "Average trips per unique device for each corridor — a proxy for repeat usage. "
    "**High value (5+):** strong commuter or regular travel pattern. "
    "**Low value (1–2):** mostly occasional or one-off trips (tourism, events). "
    "Use alongside weekday share to classify corridor demand type."
)
INFO_SCATTER = (
    "Each dot is one corridor. **X-axis** = average Haversine distance (km); "
    "**Y-axis** = trip count; **dot size** = unique devices; "
    "**colour** = weekday share (orange = leisure/weekend-led, blue = commuter/weekday-led). "
    "Use this to segment corridors: short + blue = urban commute; long + orange = regional tourism."
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading corridor data…")
def load_data(ranked_path: str, temporal_path: str):
    missing = []
    if not os.path.exists(ranked_path):
        missing.append(f"`{ranked_path}`")
    if not os.path.exists(temporal_path):
        missing.append(f"`{temporal_path}`")
    if missing:
        return None, None, (
            "Pipeline output CSV(s) not found: " + ", ".join(missing)
            + ". Re-run the pipeline to generate them."
        )
    return pd.read_csv(ranked_path), pd.read_csv(temporal_path), None


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------

def compute_effective_trips(df: pd.DataFrame, period: str) -> pd.Series:
    col = PERIOD_PCT_COL.get(period)
    if col and col in df.columns:
        return (df["n_trips"] * df[col] / 100.0).round(0).astype(int)
    return df["n_trips"]


def apply_corridor_filter(df: pd.DataFrame, period: str, top_n: int) -> pd.DataFrame:
    out = df.copy()
    out["effective_trips"] = compute_effective_trips(out, period)
    out = out.sort_values("effective_trips", ascending=False).head(top_n)
    return out.reset_index(drop=True)


def filter_temporal(temporal_df: pd.DataFrame, corridors_df: pd.DataFrame, day_type: str) -> pd.DataFrame:
    t = temporal_df.merge(
        corridors_df[["origin_lga", "dest_lga"]],
        on=["origin_lga", "dest_lga"],
        how="inner",
    )
    if day_type != "All":
        t = t[t["day_type"] == day_type]
    return t.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------

def build_flow_map(df: pd.DataFrame) -> go.Figure:
    """Plotly Scattermapbox flow map with quartile-coloured arcs."""
    fig = go.Figure()
    if df.empty:
        fig.update_layout(
            mapbox=dict(style="carto-positron", center=dict(lat=-37.0, lon=144.5), zoom=5.5),
            margin=dict(l=0, r=0, t=0, b=0), height=430, paper_bgcolor="white",
        )
        return fig

    trips = df["effective_trips"]
    q25, q50, q75 = trips.quantile(0.25), trips.quantile(0.50), trips.quantile(0.75)
    thresholds = [q75, q50, q25, trips.min() - 1]

    for i, (color, width, opacity, label) in enumerate(ARC_BUCKETS):
        lo = thresholds[i]
        hi = trips.max() + 1 if i == 0 else thresholds[i - 1]
        bucket = df[(trips >= lo) & (trips < hi)]
        if bucket.empty:
            continue

        lats, lons = [], []
        for _, r in bucket.iterrows():
            lats += [r["origin_centroid_lat"], r["dest_centroid_lat"], None]
            lons += [r["origin_centroid_lon"], r["dest_centroid_lon"], None]

        fig.add_trace(go.Scattermapbox(
            lat=lats, lon=lons,
            mode="lines",
            line=dict(color=color, width=width),
            opacity=opacity,
            name=label,
            hoverinfo="skip",
            showlegend=True,
        ))

    df2 = df.copy()
    df2["mid_lat"] = (df2["origin_centroid_lat"] + df2["dest_centroid_lat"]) / 2
    df2["mid_lon"] = (df2["origin_centroid_lon"] + df2["dest_centroid_lon"]) / 2
    df2["corridor"] = df2["origin_lga"] + " → " + df2["dest_lga"]

    fig.add_trace(go.Scattermapbox(
        lat=df2["mid_lat"],
        lon=df2["mid_lon"],
        mode="markers",
        marker=dict(size=10, color="rgba(0,0,0,0)"),
        text=df2["corridor"],
        customdata=df2[["effective_trips", "avg_distance_km"]].values,
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Trips: %{customdata[0]:,}<br>"
            "Avg dist: %{customdata[1]:.1f} km"
            "<extra></extra>"
        ),
        name="Corridors",
        showlegend=False,
    ))

    origins = df.drop_duplicates("origin_lga")
    fig.add_trace(go.Scattermapbox(
        lat=origins["origin_centroid_lat"],
        lon=origins["origin_centroid_lon"],
        mode="markers",
        marker=dict(size=7, color=C_NAVY, opacity=0.85),
        text=origins["origin_lga"],
        hovertemplate="%{text}<extra></extra>",
        name="LGA nodes",
        showlegend=False,
    ))

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=-37.0, lon=144.5), zoom=5.5),
        margin=dict(l=0, r=0, t=0, b=0),
        height=430,
        paper_bgcolor="white",
        legend=dict(
            orientation="v", x=0.01, y=0.99,
            xanchor="left", yanchor="top",
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor=C_BORDER, borderwidth=1,
            font=dict(size=10),
        ),
    )
    return fig


def build_bar_chart(df: pd.DataFrame) -> go.Figure:
    bar_df = df.copy()
    bar_df["corridor"] = bar_df["origin_lga"] + " → " + bar_df["dest_lga"]
    bar_df["bar_color"] = np.where(bar_df["pct_weekday"] >= 50, C_BLUE, C_ORANGE)

    display_n = min(30, len(bar_df))
    bar_plot = bar_df.head(display_n)

    fig = go.Figure(go.Bar(
        x=bar_plot["effective_trips"],
        y=bar_plot["corridor"],
        orientation="h",
        marker_color=bar_plot["bar_color"].tolist(),
        customdata=bar_plot[["avg_distance_km", "pct_weekday", "pct_weekend"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Trips: %{x:,}<br>"
            "Avg dist: %{customdata[0]:.1f} km<br>"
            "Weekday: %{customdata[1]:.1f}%  Weekend: %{customdata[2]:.1f}%"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        margin=dict(l=0, r=8, t=28, b=30),
        height=430,
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
        xaxis=dict(title="Trips", gridcolor=C_GRID, tickfont=dict(size=10)),
        showlegend=False,
        annotations=[dict(
            x=0.99, y=1.06, xref="paper", yref="paper",
            text=(
                f"<span style='color:{C_BLUE}'>■</span> Weekday dominant  "
                f"<span style='color:{C_ORANGE}'>■</span> Weekend dominant"
            ),
            showarrow=False, font=dict(size=9.5), xanchor="right",
        )],
    )
    return fig, display_n


def build_region_heatmap(df: pd.DataFrame) -> go.Figure:
    pivot = (
        df.groupby(["origin_tourism_region", "dest_tourism_region"])["effective_trips"]
        .sum()
        .unstack(fill_value=0)
    )
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=list(pivot.columns),
        y=list(pivot.index),
        colorscale=[[0.0, "#f0f7ff"], [0.3, C_SKY], [0.7, C_BLUE], [1.0, C_NAVY]],
        hoverongaps=False,
        hovertemplate="Origin: %{y}<br>Dest: %{x}<br>Trips: %{z:,}<extra></extra>",
        colorbar=dict(title="Trips", thickness=11, len=0.88),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=8, b=0),
        height=max(220, len(pivot.index) * 32),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(tickangle=-35, tickfont=dict(size=10), title="Destination Region"),
        yaxis=dict(tickfont=dict(size=10), title="Origin Region", autorange="reversed"),
    )
    return fig


def build_lga_heatmap(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot_table(
        index="origin_lga", columns="dest_lga",
        values="effective_trips", aggfunc="sum", fill_value=0,
    )
    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=list(pivot.columns),
        y=list(pivot.index),
        colorscale=[[0.0, "#f0f7ff"], [0.3, C_SKY], [0.7, C_BLUE], [1.0, C_NAVY]],
        hoverongaps=False,
        hovertemplate="Origin: %{y}<br>Dest: %{x}<br>Trips: %{z:,}<extra></extra>",
        colorbar=dict(title="Trips", thickness=11, len=0.9),
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=8, b=0),
        height=max(260, len(pivot.index) * 28),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(tickangle=-35, tickfont=dict(size=10), title="Destination LGA"),
        yaxis=dict(tickfont=dict(size=10), title="Origin LGA", autorange="reversed"),
    )
    return fig


def build_temporal_chart(temporal_df: pd.DataFrame, n_corridors: int, day_type: str) -> go.Figure:
    hourly = (
        temporal_df
        .groupby(["hour_of_day", "day_type"])["n_trips"]
        .sum()
        .reset_index()
    )
    fig = px.line(
        hourly, x="hour_of_day", y="n_trips", color="day_type",
        color_discrete_map={"Weekday": C_BLUE, "Weekend": C_ORANGE},
        markers=True,
        labels={"hour_of_day": "Hour of Day", "n_trips": "Trips", "day_type": "Day Type"},
    )
    for x0, x1, label in [(7, 9, "AM Peak"), (16, 18, "PM Peak")]:
        fig.add_vrect(
            x0=x0, x1=x1, fillcolor="#e0f2fe", opacity=0.45, line_width=0,
            annotation_text=label, annotation_position="top left",
            annotation_font_size=9.5,
        )
    fig.update_traces(marker=dict(size=5))
    fig.update_layout(
        margin=dict(l=0, r=0, t=12, b=30),
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(
            tickvals=list(range(0, 24, 2)),
            ticktext=[f"{h:02d}:00" for h in range(0, 24, 2)],
            gridcolor=C_GRID,
        ),
        yaxis=dict(gridcolor=C_GRID),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
    )
    return fig


def build_intensity_chart(df: pd.DataFrame) -> go.Figure:
    idf = df.copy()
    idf["corridor"] = idf["origin_lga"] + " → " + idf["dest_lga"]
    idf["trips_per_device"] = (idf["n_trips"] / idf["n_devices"]).round(1)
    idf = idf.sort_values("trips_per_device", ascending=True).tail(min(30, len(idf)))

    fig = go.Figure(go.Bar(
        x=idf["trips_per_device"],
        y=idf["corridor"],
        orientation="h",
        marker=dict(
            color=idf["trips_per_device"],
            colorscale=[[0, C_SKY], [0.5, C_BLUE], [1, C_NAVY]],
            showscale=False,
        ),
        customdata=idf[["n_trips", "n_devices"]].values,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Trips/device: %{x:.1f}<br>"
            "Total trips: %{customdata[0]:,}<br>"
            "Unique devices: %{customdata[1]:,}"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        margin=dict(l=0, r=8, t=10, b=30),
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        yaxis=dict(tickfont=dict(size=10)),
        xaxis=dict(title="Avg trips per device", gridcolor=C_GRID, tickfont=dict(size=10)),
    )
    return fig


def build_scatter(df: pd.DataFrame) -> go.Figure:
    sdf = df.copy()
    sdf["corridor"] = sdf["origin_lga"] + " → " + sdf["dest_lga"]
    fig = px.scatter(
        sdf,
        x="avg_distance_km",
        y="effective_trips",
        size="n_devices",
        color="pct_weekday",
        color_continuous_scale=[[0, C_ORANGE], [0.5, "#a78bfa"], [1, C_BLUE]],
        hover_name="corridor",
        hover_data={"avg_distance_km": ":.1f", "effective_trips": ":,", "n_devices": ":,", "pct_weekday": ":.1f"},
        labels={
            "avg_distance_km": "Avg Distance (km)",
            "effective_trips": "Trips",
            "pct_weekday": "% Weekday",
            "n_devices": "Unique Devices",
        },
        size_max=28,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=30),
        height=320,
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis=dict(gridcolor=C_GRID),
        yaxis=dict(gridcolor=C_GRID),
        coloraxis_colorbar=dict(title="% Weekday", thickness=11, len=0.85),
    )
    return fig


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

inject_css()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

ranked_raw, temporal_raw, load_error = load_data(RANKED_CSV, TEMPORAL_CSV)

if load_error:
    st.error(load_error)
    st.stop()

N_TOTAL = len(ranked_raw)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## Filters")

    st.selectbox("State", ["Victoria"])

    st.divider()

    st.markdown("**Time period**")
    period = st.selectbox(
        "Trip period", list(PERIOD_PCT_COL.keys()), index=0,
        help="Ranks corridors by trips in the selected period.",
    )

    if "Weekend" in period:
        dt_default = "Weekend"
    elif period != "All":
        dt_default = "Weekday"
    else:
        dt_default = "All"

    day_type = st.radio(
        "Temporal chart day type",
        ["All", "Weekday", "Weekend"],
        index=["All", "Weekday", "Weekend"].index(dt_default),
        help="Filters the 24-hour demand chart.",
    )

    st.divider()

    st.markdown("**Top N corridors**")

    if "top_n_val" not in st.session_state:
        st.session_state["top_n_val"] = N_TOTAL

    st.session_state["top_n_val"] = min(int(st.session_state["top_n_val"]), N_TOTAL)

    b1, b2, b3, b4 = st.columns(4)
    if b1.button("10",  use_container_width=True): st.session_state["top_n_val"] = min(10,  N_TOTAL); st.rerun()
    if b2.button("25",  use_container_width=True): st.session_state["top_n_val"] = min(25,  N_TOTAL); st.rerun()
    if b3.button("50",  use_container_width=True): st.session_state["top_n_val"] = min(50,  N_TOTAL); st.rerun()
    if b4.button("All", use_container_width=True): st.session_state["top_n_val"] = N_TOTAL;           st.rerun()

    top_n = st.number_input(
        "Enter number of corridors",
        min_value=1,
        max_value=N_TOTAL,
        value=st.session_state["top_n_val"],
        step=1,
        help=f"Type any value from 1 to {N_TOTAL:,}, or use the preset buttons above.",
        label_visibility="collapsed",
    )
    st.session_state["top_n_val"] = int(top_n)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

filtered_df   = apply_corridor_filter(ranked_raw, period, top_n)
filtered_temp = filter_temporal(temporal_raw, filtered_df, day_type)

period_label  = period if period != "All" else "All periods"

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Localis Sampledata — Network Flow Map & Rankings")
st.caption(f"Localis Sampledata · Victoria · {period_label} · **{len(filtered_df):,}** corridors shown")

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

k1, k2, k3, k4 = st.columns(4)

total_trips    = int(filtered_df["effective_trips"].sum())
unique_origins = filtered_df["origin_lga"].nunique()
unique_dests   = filtered_df["dest_lga"].nunique()
avg_dist       = filtered_df["avg_distance_km"].mean() if not filtered_df.empty else 0.0

k1.markdown(kpi_tile_html("Corridors shown",        f"{len(filtered_df):,}",   f"of {N_TOTAL:,} total"),                        unsafe_allow_html=True)
k2.markdown(kpi_tile_html("Trips (selected period)", f"{total_trips:,}",        period_label),                                   unsafe_allow_html=True)
k3.markdown(kpi_tile_html("Unique LGAs",            f"{unique_origins + unique_dests:,}", f"{unique_origins} origins · {unique_dests} dests"), unsafe_allow_html=True)
k4.markdown(kpi_tile_html("Avg corridor distance",  f"{avg_dist:.1f} km",      "Haversine between centroids"),                  unsafe_allow_html=True)

st.markdown("")

# ---------------------------------------------------------------------------
# Row 2: Flow map | Ranked bar chart
# ---------------------------------------------------------------------------

map_col, bar_col = st.columns([1.55, 1.0])

with map_col:
    chart_header("Arc Flow Map", INFO_ARC_MAP)
    st.plotly_chart(build_flow_map(filtered_df), use_container_width=True)

with bar_col:
    chart_header("Corridors Ranked by Trips", INFO_BAR)
    if filtered_df.empty:
        st.info("No data.")
    else:
        fig_bar, display_n = build_bar_chart(filtered_df)
        if display_n < len(filtered_df):
            st.caption(f"Showing top {display_n} of {len(filtered_df)} corridors")
        st.plotly_chart(fig_bar, use_container_width=True)

# ---------------------------------------------------------------------------
# Row 3: Tourism region heatmap
# ---------------------------------------------------------------------------

st.divider()
chart_header("Tourism Region OD Heatmap — Summary View", INFO_REGION_HEAT)

if filtered_df.empty or "origin_tourism_region" not in filtered_df.columns:
    st.info("No region data for current filters.")
else:
    st.plotly_chart(build_region_heatmap(filtered_df), use_container_width=True)

# ---------------------------------------------------------------------------
# Row 4: LGA OD matrix
# ---------------------------------------------------------------------------

st.divider()
chart_header("LGA OD Matrix — Detail View", INFO_LGA_MATRIX)

if filtered_df.empty:
    st.info("No corridor data for current filters.")
else:
    st.plotly_chart(build_lga_heatmap(filtered_df), use_container_width=True)

# ---------------------------------------------------------------------------
# Row 5: Temporal demand | Corridor intensity
# ---------------------------------------------------------------------------

st.divider()
temp_col, intens_col = st.columns(2)

with temp_col:
    chart_header(f"24-Hour Demand — {day_type} · Top {len(filtered_df):,} Corridors", INFO_TEMPORAL)
    if filtered_temp.empty:
        st.info("No temporal data for the current selection.")
    else:
        st.plotly_chart(build_temporal_chart(filtered_temp, len(filtered_df), day_type), use_container_width=True)

with intens_col:
    chart_header("Corridor Intensity — Avg Trips per Device", INFO_INTENSITY)
    if filtered_df.empty:
        st.info("No data.")
    else:
        st.plotly_chart(build_intensity_chart(filtered_df), use_container_width=True)

# ---------------------------------------------------------------------------
# Row 6: Distance vs volume scatter
# ---------------------------------------------------------------------------

st.divider()
sc_col, _ = st.columns([1.0, 0.05])

with sc_col:
    chart_header("Distance vs Trip Volume", INFO_SCATTER)
    if filtered_df.empty:
        st.info("No data.")
    else:
        st.plotly_chart(build_scatter(filtered_df), use_container_width=True)

# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

st.divider()
st.markdown('<div class="sec-header">Downloads</div>', unsafe_allow_html=True)

dl1, dl2, dl3 = st.columns(3)
_slug  = period.replace(" ", "_").lower()
_top   = len(filtered_df)

with dl1:
    dl_corridors = filtered_df.drop(columns=["effective_trips"], errors="ignore")
    st.download_button(
        label=f"Filtered Corridors CSV  ({_top:,} rows)",
        data=to_csv_bytes(dl_corridors),
        file_name=f"corridors_{_slug}_top{_top}.csv",
        mime="text/csv",
    )

with dl2:
    if filtered_temp.empty:
        st.button("Temporal Distribution CSV", disabled=True)
    else:
        st.download_button(
            label=f"Temporal Distribution CSV  ({len(filtered_temp):,} rows)",
            data=to_csv_bytes(filtered_temp),
            file_name=f"temporal_{day_type.lower()}_top{_top}.csv",
            mime="text/csv",
        )

with dl3:
    if filtered_temp.empty:
        st.button("Combined CSV", disabled=True)
    else:
        combined = filtered_temp.merge(
            filtered_df[["origin_lga", "dest_lga", "effective_trips", "avg_distance_km", "n_devices"]],
            on=["origin_lga", "dest_lga"], how="left",
        ).rename(columns={"effective_trips": "total_trips_period"})
        st.download_button(
            label=f"Combined CSV  ({len(combined):,} rows)",
            data=to_csv_bytes(combined),
            file_name=f"combined_{_slug}_top{_top}.csv",
            mime="text/csv",
        )
