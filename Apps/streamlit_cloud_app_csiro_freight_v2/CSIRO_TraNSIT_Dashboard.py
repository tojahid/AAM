"""
app.py  —  FreightOD: TraNSIT Metrics with Visualisations  (Page 1)

Replicates the 10 headline freight metrics for any Origin → Destination LGA pair,
then adds CSIRO-style charts (trip length, supply chain, cost breakdown) and an
industry composition donut. Navigate to Page 2 for OD corridor rankings.

Run with:
    python -m streamlit run apps/app_with_visualisation/app.py
"""

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lga_codes import LGA_NAMES, LGA_STATE, SORTED_NAMES, STATE_COLORS, STATE_LGAS
from api import (
    build_url,
    fetch_od_metrics,
    fetch_trip_length,
    fetch_supply_chain,
    fetch_logistics,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FreightOD \u2014 TraNSIT Metrics",
    page_icon="\U0001f69b",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* ── Sidebar background ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #1E3A5F;
}

/* ── All text-bearing elements in sidebar ─────────────────────────────── */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] div > small {
    color: #C8DAF0 !important;
}

/* ── Radio button text ────────────────────────────────────────────────── */
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [role="radiogroup"] label p,
[data-testid="stSidebar"] [role="radiogroup"] label span {
    color: #C8DAF0 !important;
}

/* ── Selectbox labels ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSelectbox [data-testid="stWidgetLabel"] p {
    color: #A8C8E8 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    font-weight: 600;
}

[data-testid="stSidebar"] [data-baseweb="select"] {
    border-radius: 6px !important;
}
[data-testid="stSidebarContent"] hr {
    border-color: #2E5A8C !important;
}

/* ── Section labels ──────────────────────────────────────────────────── */
.section-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #9CA3AF;
    margin-bottom: 10px;
    margin-top: 4px;
}

/* ── Metric cards ────────────────────────────────────────────────────── */
.metric-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 16px 18px;
    border-left: 4px solid #2563EB;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    height: 100%;
}
.metric-card .metric-icon {
    font-size: 18px;
    margin-bottom: 4px;
    line-height: 1;
}
.metric-card .metric-label {
    color: #6B7280;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 5px;
}
.metric-card .metric-value {
    color: #111827;
    font-size: 20px;
    font-weight: 800;
    line-height: 1.1;
}
.metric-card .metric-sub {
    color: #9CA3AF;
    font-size: 10px;
    margin-top: 3px;
}

/* ── Route header ────────────────────────────────────────────────────── */
.route-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 2px;
}
.route-title {
    font-size: 24px;
    font-weight: 800;
    color: #111827;
    margin: 0;
    line-height: 1.2;
}
.state-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    color: white;
    letter-spacing: 0.4px;
}
.lga-chip {
    display: inline-block;
    background: #F3F4F6;
    color: #374151;
    padding: 3px 10px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid #E5E7EB;
}
.route-subtitle {
    color: #6B7280;
    font-size: 13px;
    margin-top: 4px;
}

/* ── Helper text ─────────────────────────────────────────────────────── */
.helper-text {
    font-size: 12px;
    color: #6B7280;
    margin-bottom: 12px;
}

/* ── Table ───────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}

/* ── Download button ─────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
    background-color: #1E3A5F !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 8px 18px !important;
}
[data-testid="stDownloadButton"] button:hover {
    background-color: #2B5080 !important;
}

/* ── Expander ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
}

/* ── Main padding ────────────────────────────────────────────────────── */
.main .block-container {
    padding-top: 1.5rem;
}

/* ── Info popover trigger button ─────────────────────────────────────── */
[data-testid="stPopover"] button {
    background: none !important;
    border: 1px solid #BFDBFE !important;
    color: #2563EB !important;
    font-size: 12px !important;
    padding: 2px 6px !important;
    font-weight: 700 !important;
    min-height: 0 !important;
    height: 26px !important;
    border-radius: 4px !important;
    box-shadow: none !important;
    line-height: 1 !important;
    margin-top: 1px !important;
}
[data-testid="stPopover"] button:hover {
    background: #EFF6FF !important;
    border-color: #93C5FD !important;
    color: #1D4ED8 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Cached API calls
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_metrics(orig_lga: str, dest_lga: str, mode: str | None):
    return fetch_od_metrics(orig_lga, dest_lga, mode)

@st.cache_data(show_spinner=False)
def get_trip_length(orig_lga: str, dest_lga: str, mode: str | None):
    return fetch_trip_length(orig_lga, dest_lga, mode)

@st.cache_data(show_spinner=False)
def get_supply_chain(orig_lga: str, dest_lga: str, mode: str | None):
    return fetch_supply_chain(orig_lga, dest_lga, mode)

@st.cache_data(show_spinner=False)
def get_logistics(orig_lga: str, dest_lga: str, mode: str | None):
    return fetch_logistics(orig_lga, dest_lga, mode)


# ---------------------------------------------------------------------------
# Helper: metric card HTML
# ---------------------------------------------------------------------------

def metric_card(label: str, value: str, icon: str, color: str, sub: str = "") -> str:
    sub_html = f'<div class="metric-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="metric-card" style="border-left-color: {color};">
        <div class="metric-icon">{icon}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {sub_html}
    </div>
    """


def fmt_money(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.1f}M"
    return f"${v:,.0f}"


def _safe_name(name: str) -> str:
    return name.replace(" ", "_").replace("(", "").replace(")", "").strip("_")


def chart_header(title: str, info_md: str, section: bool = True) -> None:
    """Render a chart/section title with a clickable ⓘ info popover."""
    col_t, col_i = st.columns([0.88, 0.12])
    with col_t:
        if section:
            st.markdown(
                f'<div class="section-label">{title}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-weight:700; font-size:14px; color:#111827; '
                f'margin-bottom:4px; line-height:1.3;">{title}</div>',
                unsafe_allow_html=True,
            )
    with col_i:
        with st.popover("ⓘ"):
            st.markdown(info_md)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 16px 0;">
        <div style="font-size:22px; font-weight:800; color:white; letter-spacing:-0.3px;">
            🚛 FreightOD
        </div>
        <div style="font-size:13px; font-weight:600; color:#A8D4F5; margin-top:2px; letter-spacing:0.2px;">
            TraNSIT Metrics
        </div>
        <div style="font-size:12px; color:#7BA7CC; margin-top:6px; line-height:1.5;">
            Origin &rarr; Destination road freight metrics<br>
            CSIRO TraNSIT &middot; SIM-AU-BASELINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
<div style="background:linear-gradient(135deg,#0D3B6E,#1565C0);
     border-left:4px solid #42A5F5; border-radius:6px;
     padding:10px 12px; margin:4px 0 12px 0;">
    <div style="font-size:10px; font-weight:700; color:#90CAF9;
         text-transform:uppercase; letter-spacing:0.8px; margin-bottom:4px;">
        📊 Page 1 of 2
    </div>
    <div style="font-size:12px; color:#E3F2FD; line-height:1.5;">
        <strong>OD Freight Metrics</strong><br>
        Select an Origin → Destination pair to view freight costs,
        volumes, and transport breakdowns for that corridor.
    </div>
</div>
""", unsafe_allow_html=True)

    # ── ORIGIN ────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Origin</div>',
        unsafe_allow_html=True,
    )

    orig_state_opts = ["All states"] + list(STATE_LGAS.keys())
    orig_state = st.selectbox(
        "Origin State",
        options=orig_state_opts,
        index=orig_state_opts.index("VIC"),
        key="orig_state_sel",
        label_visibility="collapsed",
    )

    orig_lga_opts = SORTED_NAMES if orig_state == "All states" else STATE_LGAS[orig_state]

    if "orig_lga_name" not in st.session_state:
        st.session_state["orig_lga_name"] = "Melbourne (C)"
    if st.session_state["orig_lga_name"] not in orig_lga_opts:
        st.session_state["orig_lga_name"] = orig_lga_opts[0]

    orig_name = st.selectbox(
        "Origin LGA",
        options=orig_lga_opts,
        index=orig_lga_opts.index(st.session_state["orig_lga_name"]),
        label_visibility="collapsed",
    )
    st.session_state["orig_lga_name"] = orig_name
    orig_code = LGA_NAMES[orig_name]
    orig_state_abbr = LGA_STATE[orig_code]

    st.markdown(
        f'<div style="margin-top:4px; margin-bottom:4px;">'
        f'<span class="lga-chip" style="background:#2E5A8C; color:#A8D4F5; '
        f'border-color:#3B6FA0; font-size:11px;">{orig_code}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── DESTINATION ───────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Destination</div>',
        unsafe_allow_html=True,
    )

    dest_state_opts = ["All states"] + list(STATE_LGAS.keys())
    dest_state = st.selectbox(
        "Destination State",
        options=dest_state_opts,
        index=dest_state_opts.index("VIC"),
        key="dest_state_sel",
        label_visibility="collapsed",
    )

    dest_lga_opts = SORTED_NAMES if dest_state == "All states" else STATE_LGAS[dest_state]

    if "dest_lga_name" not in st.session_state:
        st.session_state["dest_lga_name"] = "Melbourne (C)"
    if st.session_state["dest_lga_name"] not in dest_lga_opts:
        st.session_state["dest_lga_name"] = dest_lga_opts[0]

    dest_name = st.selectbox(
        "Destination LGA",
        options=dest_lga_opts,
        index=dest_lga_opts.index(st.session_state["dest_lga_name"]),
        label_visibility="collapsed",
    )
    st.session_state["dest_lga_name"] = dest_name
    dest_code = LGA_NAMES[dest_name]
    dest_state_abbr = LGA_STATE[dest_code]

    st.markdown(
        f'<div style="margin-top:4px; margin-bottom:4px;">'
        f'<span class="lga-chip" style="background:#2E5A8C; color:#A8D4F5; '
        f'border-color:#3B6FA0; font-size:11px;">{dest_code}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.divider()

    # ── TRANSPORT MODE ────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Transport Mode</div>',
        unsafe_allow_html=True,
    )

    MODE_OPTIONS = {
        "Road":      "road",
        "Rail":      "rail",
        "All Modes": None,
    }

    mode_label = st.selectbox(
        "Transport Mode",
        options=list(MODE_OPTIONS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    selected_mode = MODE_OPTIONS[mode_label]

    if mode_label == "Rail":
        st.markdown(
            '<div style="font-size:10px; color:#EF4444; margin-top:4px; line-height:1.5;">'
            '&#10006; Rail OD data is <strong>not available</strong> in the '
            '<code>commodityreport</code> endpoint. Select Road to view OD metrics.'
            '</div>',
            unsafe_allow_html=True,
        )
    elif mode_label == "All Modes":
        st.markdown(
            '<div style="font-size:10px; color:#F59E0B; margin-top:4px; line-height:1.5;">'
            '&#9888; <code>commodityreport</code> is a road-only endpoint. '
            '"All Modes" returns the same values as Road.'
            '</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown(
        '<div style="color:#5A8AB0; font-size:11px; line-height:1.7;">'
        'FreightOD &mdash; TraNSIT Metrics<br>'
        'Dataset: SIM-AU-BASELINE<br>'
        'Endpoint: commodityreport<br>'
        f'Mode: {mode_label} &nbsp;&middot;&nbsp; Metric: cost/tonne'
        '</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Save shared session state for Page 2
# ---------------------------------------------------------------------------

st.session_state["shared_orig_code"]  = orig_code
st.session_state["shared_orig_name"]  = orig_name
st.session_state["shared_orig_state"] = orig_state_abbr
st.session_state["shared_dest_code"]  = dest_code
st.session_state["shared_dest_name"]  = dest_name

# ---------------------------------------------------------------------------
# Route header
# ---------------------------------------------------------------------------

orig_badge = STATE_COLORS.get(orig_state_abbr, "#4B5563")
dest_badge = STATE_COLORS.get(dest_state_abbr, "#4B5563")

st.markdown(f"""
<div class="route-header">
    <span class="route-title">{orig_name}</span>
    <span class="state-badge" style="background-color:{orig_badge};">{orig_state_abbr}</span>
    <span class="lga-chip">{orig_code}</span>
    <span style="font-size:22px; color:#9CA3AF; font-weight:300;">&#8594;</span>
    <span class="route-title">{dest_name}</span>
    <span class="state-badge" style="background-color:{dest_badge};">{dest_state_abbr}</span>
    <span class="lga-chip">{dest_code}</span>
</div>
<div class="route-subtitle">
    OD headline freight metrics &nbsp;&middot;&nbsp; SIM-AU-BASELINE &nbsp;&middot;&nbsp;
    {mode_label}{"  (road-equivalent)" if mode_label == "All Modes" else ""}
</div>
""", unsafe_allow_html=True)

with st.expander("API endpoint used", expanded=False):
    st.code(build_url(orig_code, dest_code, selected_mode), language="text")

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Rail block
# ---------------------------------------------------------------------------

if mode_label == "Rail":
    st.error(
        "**Rail OD metrics are not available.**\n\n"
        "The `commodityreport` endpoint is **road-only**. "
        "Rail freight data exists only in the density map endpoint at a broader level.\n\n"
        "**To see OD headline metrics, select Road.**",
        icon="\U0001f6ab",
    )
    st.stop()

if mode_label == "All Modes":
    st.info(
        "**All Modes note:** The `commodityreport` endpoint is road-only. "
        "Omitting the mode filter returns the same data as Road. "
        "The values shown below are road freight metrics.",
        icon="\u2139\ufe0f",
    )

# ---------------------------------------------------------------------------
# Fetch commodityreport data
# ---------------------------------------------------------------------------

with st.spinner(f"Fetching {orig_name} \u2192 {dest_name}\u2026"):
    records, totals, error = get_metrics(orig_code, dest_code, selected_mode)

if error:
    st.error(f"**API Error:** {error}")
    st.stop()

if not records:
    st.info(
        f"**No data for {orig_name} \u2192 {dest_name}.**\n\n"
        "Possible reasons:\n"
        "- Freight volume is too low (statistical suppression rule)\n"
        "- No modelled road freight flow between these two LGAs\n"
        "- Try the reverse direction, or a nearby LGA pair\n\n"
        "**Known working examples:** Melbourne \u2192 Melbourne, "
        "Melbourne \u2192 Albury, Melbourne \u2192 Sydney, Melbourne \u2192 Brisbane",
        icon="\u2139\ufe0f",
    )
    st.stop()

# ---------------------------------------------------------------------------
# Section 1 — 10 Headline Metric Cards
# ---------------------------------------------------------------------------

chart_header("Headline Metrics", """
**What are Headline Metrics?**

These 10 cards summarise all freight flowing on this Origin → Destination corridor for a full year (annualised model estimate).

Values are aggregated from per-industry records returned by the `commodityreport` API:
- **Annual Tonnes / Trailers** — SUM across all industry groups
- **Cost per Tonne** — SUM(transport costs) ÷ SUM(tonnes)
- **Avg Trip Distance / Duration** — weighted average by trip count

*Source: CSIRO TraNSIT · SIM-AU-BASELINE · commodityreport endpoint · Road mode only*
""")
st.markdown(
    f'<div class="helper-text">'
    f'These values match the TraNSIT dashboard when this OD pair is selected. '
    f'Computed from {totals["commodities_count"]} '
    f'industr{"y" if totals["commodities_count"] == 1 else "y groups"} '
    f'({totals["total_trips"]:,} trips total).'
    f'</div>',
    unsafe_allow_html=True,
)

r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)

with r1c1:
    st.markdown(metric_card(
        "Annual Tonnes", f"{totals['annual_tonnes']:,.0f} t",
        "\u2696\ufe0f", "#2563EB", "SUM(tonnes)",
    ), unsafe_allow_html=True)

with r1c2:
    st.markdown(metric_card(
        "Annual Trailers", f"{totals['annual_trailers']:,.0f}",
        "\U0001f69b", "#4F46E5", "SUM(trailer_loads)",
    ), unsafe_allow_html=True)

with r1c3:
    st.markdown(metric_card(
        "Cost per Tonne", f"${totals['cost_per_tonne']:,.2f}",
        "\U0001f4b2", "#059669", "SUM(costs) / SUM(tonnes)",
    ), unsafe_allow_html=True)

with r1c4:
    st.markdown(metric_card(
        "Total Transport Costs", fmt_money(totals["total_transport_costs"]),
        "\U0001f4b8", "#0D9488", f"${totals['total_transport_costs']:,.0f}",
    ), unsafe_allow_html=True)

with r1c5:
    st.markdown(metric_card(
        "Total Freight Value", fmt_money(totals["total_freight_value"]),
        "\U0001f4b0", "#D97706", f"${totals['total_freight_value']:,.0f}",
    ), unsafe_allow_html=True)

st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns(5)

with r2c1:
    st.markdown(metric_card(
        "Total Travel Distance", f"{totals['total_travel_distance_km']:,.0f} km",
        "\U0001f5fa\ufe0f", "#7C3AED", "SUM(total_trip_distance)",
    ), unsafe_allow_html=True)

with r2c2:
    st.markdown(metric_card(
        "Annual Tonne-km", f"{totals['annual_tonne_km']:,.0f}",
        "\U0001f4cf", "#9333EA", "SUM(tonne_kms)",
    ), unsafe_allow_html=True)

with r2c3:
    st.markdown(metric_card(
        "Avg Trip Distance", f"{totals['avg_trip_distance_km']:,.1f} km",
        "\U0001f4cd", "#0284C7", "weighted avg by trip count",
    ), unsafe_allow_html=True)

with r2c4:
    st.markdown(metric_card(
        "Avg Trip Duration", f"{totals['avg_trip_duration_hrs']:.2f} hrs",
        "\u23f1\ufe0f", "#0369A1", "weighted avg by trip count",
    ), unsafe_allow_html=True)

with r2c5:
    st.markdown(metric_card(
        "Total CO\u2082 Emissions", f"{totals['total_co2_t']:,.1f} t",
        "\U0001f33f", "#DC2626", "SUM(co2_tn)",
    ), unsafe_allow_html=True)

st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Section 2 — Industry Breakdown Table
# ---------------------------------------------------------------------------

chart_header("Industry Breakdown", """
**What is the Industry Breakdown table?**

Each row represents one **industry group** (Level 2 commodity classification) returned by the API with `groupBy_l2=true`.

Summing any numeric column across all rows produces the corresponding headline metric above. The **TOTAL** row equals the sum of all industry rows.

> **Note on suppression:** Some industries may be absent for low-volume corridors — the API omits records below a statistical threshold.
""")
st.markdown(
    '<div class="helper-text">'
    'Raw per-industry records returned by the API. '
    'Summing each numeric column produces the headline metrics above. '
    'The <strong>TOTAL</strong> row is the sum of all industry rows.'
    '</div>',
    unsafe_allow_html=True,
)

commodity_rows = []
for r in records:
    commodity_rows.append({
        "Industry":           r.get("industry", ""),
        "Sector":             r.get("sector", ""),
        "Trips":              r.get("trips_count", 0),
        "Tonnes":             r.get("tonnes", 0.0),
        "Trailers":           r.get("trailer_loads", 0.0),
        "Transport Cost ($)": r.get("trip_transport_costs", 0.0),
        "Freight Value ($)":  r.get("total_freight_value", 0.0),
        "Cost/t ($)":         r.get("cst_per_tonne", 0.0),
        "Tonne-km":           r.get("tonne_kms", 0.0),
        "Total Distance (km)": r.get("total_trip_distance", 0.0),
        "CO2 (t)":            r.get("co2_tn", 0.0),
    })

df_commodities = pd.DataFrame(commodity_rows)

total_row = {
    "Industry":           "TOTAL",
    "Sector":             "",
    "Trips":              totals["total_trips"],
    "Tonnes":             totals["annual_tonnes"],
    "Trailers":           totals["annual_trailers"],
    "Transport Cost ($)": totals["total_transport_costs"],
    "Freight Value ($)":  totals["total_freight_value"],
    "Cost/t ($)":         totals["cost_per_tonne"],
    "Tonne-km":           totals["annual_tonne_km"],
    "Total Distance (km)": totals["total_travel_distance_km"],
    "CO2 (t)":            totals["total_co2_t"],
}
df_display = pd.concat(
    [df_commodities, pd.DataFrame([total_row])],
    ignore_index=True,
)

st.dataframe(
    df_display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Industry":           st.column_config.TextColumn(width="medium"),
        "Sector":             st.column_config.TextColumn(width="small"),
        "Trips":              st.column_config.NumberColumn(format="%d", width="small"),
        "Tonnes":             st.column_config.NumberColumn(format="%.1f"),
        "Trailers":           st.column_config.NumberColumn(format="%.1f"),
        "Transport Cost ($)": st.column_config.NumberColumn(format="$%.0f"),
        "Freight Value ($)":  st.column_config.NumberColumn(format="$%.0f"),
        "Cost/t ($)":         st.column_config.NumberColumn(format="$%.2f", width="small"),
        "Tonne-km":           st.column_config.NumberColumn(format="%.1f"),
        "Total Distance (km)": st.column_config.NumberColumn(format="%.1f"),
        "CO2 (t)":            st.column_config.NumberColumn(format="%.2f", width="small"),
    },
)

_context = {
    "origin_lga_name": orig_name,
    "origin_lga_code": orig_code,
    "dest_lga_name":   dest_name,
    "dest_lga_code":   dest_code,
}

df_industry_export = pd.DataFrame(
    [{**_context, **row} for row in df_display.to_dict("records")]
)
df_metrics_export = pd.DataFrame([{
    **_context,
    "Annual Tonnes":              totals["annual_tonnes"],
    "Annual Trailers":            totals["annual_trailers"],
    "Cost per Tonne":             totals["cost_per_tonne"],
    "Total Transport Costs":      totals["total_transport_costs"],
    "Total Freight Value":        totals["total_freight_value"],
    "Total Travel Distance (km)": totals["total_travel_distance_km"],
    "Annual Tonne-km":            totals["annual_tonne_km"],
    "Avg Trip Distance (km)":     totals["avg_trip_distance_km"],
    "Avg Trip Duration (hrs)":    totals["avg_trip_duration_hrs"],
    "Total CO2 Emissions (t)":    totals["total_co2_t"],
}])

_orig = _safe_name(orig_name)
_dest = _safe_name(dest_name)

col_dl1, col_dl2, _ = st.columns([1, 1, 4])
with col_dl1:
    st.download_button(
        label="\u2b07 Per-Industry CSV",
        data=df_industry_export.to_csv(index=False).encode("utf-8"),
        file_name=f"od_{_orig}_to_{_dest}_per_industry_metrics.csv",
        mime="text/csv",
        use_container_width=True,
    )
with col_dl2:
    st.download_button(
        label="\u2b07 Headline Metrics CSV",
        data=df_metrics_export.to_csv(index=False).encode("utf-8"),
        file_name=f"od_{_orig}_to_{_dest}_metrics.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.markdown("<div style='margin-top:32px;'></div>", unsafe_allow_html=True)
st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Freight Profile Charts (CSIRO-style)
# ---------------------------------------------------------------------------

chart_header("Freight Profile Charts", """
**Freight Profile Charts**

Four charts providing a deeper view of this corridor's freight characteristics, each using a separate TraNSIT API endpoint:
- **A1** Trip Length Distribution — *triplengthreport*
- **A2** Supply Chain Flows — *supplychainreport*
- **A3** Transport Cost Breakdown — *transportlogisticsreport*
- **B4** Freight Composition Donut — *commodityreport*
""")
st.markdown(
    '<div class="helper-text">'
    'Charts replicating the CSIRO TraNSIT dashboard visualisations for this OD corridor.'
    '</div>',
    unsafe_allow_html=True,
)

# Colour palette
_BLUE   = "#2563EB"
_ORANGE = "#F97316"
_GREEN  = "#10B981"
_RED    = "#DC2626"
_PURPLE = "#7C3AED"
_AMBER  = "#D97706"
_TEAL   = "#0D9488"
_INDIGO = "#4F46E5"

_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

chart_col1, chart_col2 = st.columns(2)

# ── A1 — Trip Length Distribution ─────────────────────────────────────────
with chart_col1:
    with st.spinner("Loading trip length data…"):
        tl_records, tl_error = get_trip_length(orig_code, dest_code, selected_mode)

    chart_header("Trip Length Distribution", """
**A1 — Trip Length Distribution**

Shows how freight on this corridor splits across three trip length categories:
- **Short** — trips up to ~100 km
- **Medium** — trips from ~100 to ~500 km
- **Long** — trips over ~500 km

Each bar group represents one commodity sector. Toggle between **Tonnes** and **Trips** to compare whether short or long trips dominate by freight volume or trip frequency.

*Source: triplengthreport endpoint*
""", section=False)
    if tl_error:
        st.warning(f"Could not load trip length data: {tl_error}")
    elif not tl_records:
        st.info("No trip length data for this OD pair.")
    else:
        tl_metric = st.radio(
            "Measure",
            ["Tonnes", "Trips"],
            horizontal=True,
            key="tl_metric",
            label_visibility="collapsed",
        )
        tl_field = "tonnes" if tl_metric == "Tonnes" else "trips"

        # Build grouped bar: x=trip_type, group=commod_l3
        sectors = sorted({r.get("commod_l3", "") for r in tl_records})
        trip_types = ["Short", "Medium", "Long"]
        sector_colors = [_BLUE, _ORANGE, _GREEN, _PURPLE, _TEAL, _AMBER]

        fig_tl = go.Figure()
        for i, sector in enumerate(sectors):
            x_vals, y_vals = [], []
            for tt in trip_types:
                match = next(
                    (r for r in tl_records
                     if r.get("commod_l3") == sector and r.get("trip_type") == tt),
                    None,
                )
                x_vals.append(tt)
                y_vals.append(match.get(tl_field, 0) if match else 0)
            fig_tl.add_trace(go.Bar(
                name=sector.capitalize(),
                x=x_vals,
                y=y_vals,
                marker_color=sector_colors[i % len(sector_colors)],
                hovertemplate=f"<b>{sector.capitalize()}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>",
            ))

        fig_tl.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="group",
            xaxis_title="Trip Type",
            yaxis_title=tl_metric,
            legend=dict(orientation="h", y=-0.2),
            height=320,
        )
        st.plotly_chart(fig_tl, use_container_width=True)

# ── A2 — Supply Chain Node Flows ───────────────────────────────────────────
with chart_col2:
    with st.spinner("Loading supply chain data…"):
        sc_records, sc_error = get_supply_chain(orig_code, dest_code, selected_mode)

    chart_header("Supply Chain Flows", """
**A2 — Supply Chain Flows**

Shows which supply chain node types are connected on this corridor.

`orig_type` and `dest_type` describe the role of each endpoint — for example: Farm, Processor, Distribution Centre, Port, Warehouse, or Retail.

Bars are sorted largest to smallest by tonnes. Hover a bar to see trips, cost per tonne, and CO₂ for that flow type.

Useful for understanding whether this corridor serves farm-to-processor, port-to-warehouse, or urban distribution supply chains.

*Source: supplychainreport endpoint*
""", section=False)
    if sc_error:
        st.warning(f"Could not load supply chain data: {sc_error}")
    elif not sc_records:
        st.info("No supply chain data for this OD pair.")
    else:
        sc_records_sorted = sorted(sc_records, key=lambda r: r.get("tonnes", 0), reverse=True)
        sc_labels = [f"{r.get('orig_type', '?')} → {r.get('dest_type', '?')}" for r in sc_records_sorted]
        sc_tonnes = [r.get("tonnes", 0) for r in sc_records_sorted]
        sc_colors = [_BLUE, _ORANGE, _GREEN, _PURPLE, _TEAL, _AMBER, _RED, _INDIGO]

        fig_sc = go.Figure(go.Bar(
            x=sc_tonnes,
            y=sc_labels,
            orientation="h",
            marker_color=[sc_colors[i % len(sc_colors)] for i in range(len(sc_labels))],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Tonnes: %{x:,.0f}<br>"
                "Trips: %{customdata[0]}<br>"
                "Cost/t: $%{customdata[1]:.2f}<br>"
                "CO₂: %{customdata[2]:,.1f} t<extra></extra>"
            ),
            customdata=[
                [r.get("trips", 0), r.get("cst_per_tonne", 0), r.get("co2_tn", 0)]
                for r in sc_records_sorted
            ],
        ))
        fig_sc.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Tonnes",
            yaxis_autorange="reversed",
            height=320,
        )
        st.plotly_chart(fig_sc, use_container_width=True)

st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

chart_col3, chart_col4 = st.columns(2)

# ── A3 — Transport Cost Breakdown ─────────────────────────────────────────
with chart_col3:
    with st.spinner("Loading logistics cost data…"):
        lg_records, lg_error = get_logistics(orig_code, dest_code, selected_mode)

    chart_header("Transport Cost Breakdown", """
**A3 — Transport Cost Breakdown**

Stacked horizontal bars showing how total transport cost is composed for each commodity sector.

> **Note:** Values are **total annual costs in AUD**, not cost per tonne. Higher-volume sectors will therefore appear larger even if their cost per tonne is similar to smaller sectors.

| Component | Description |
|---|---|
| Capital | Vehicle purchase / depreciation |
| Driver | Labour and driver wages |
| Fuel | Fuel consumption |
| Fixed | Registration, insurance, overhead |
| Maintenance | Vehicle servicing |
| Load | Loading time at origin |
| Unload | Unloading time at destination |

Longer corridors typically show higher Fuel and Driver proportions. Sectors with many small loads show higher Load/Unload proportions.

*Source: transportlogisticsreport endpoint*
""", section=False)
    if lg_error:
        st.warning(f"Could not load logistics data: {lg_error}")
    elif not lg_records:
        st.info("No logistics cost data for this OD pair.")
    else:
        cost_components = [
            ("Capital",      "capital_cost",      "#2563EB"),
            ("Driver",       "driver_cost",        "#4F46E5"),
            ("Fuel",         "fuel_cost",          "#F97316"),
            ("Fixed",        "fixed_cost",         "#0D9488"),
            ("Maintenance",  "maintenance_cost",   "#7C3AED"),
            ("Load",         "load_c",             "#059669"),
            ("Unload",       "unload_c",           "#D97706"),
        ]
        lg_sectors = [r.get("commod_l3", "").capitalize() for r in lg_records]

        fig_lg = go.Figure()
        for label, field, color in cost_components:
            vals = [r.get(field, 0) for r in lg_records]
            if any(v > 0 for v in vals):
                fig_lg.add_trace(go.Bar(
                    name=label,
                    y=lg_sectors,
                    x=vals,
                    orientation="h",
                    marker_color=color,
                    hovertemplate=f"<b>{label}</b>: $%{{x:,.0f}}<extra></extra>",
                ))

        fig_lg.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="stack",
            xaxis_title="Cost (AUD)",
            height=320,
            legend=dict(orientation="h", y=-0.25),
        )
        st.plotly_chart(fig_lg, use_container_width=True)

# ── B4 — Industry Composition Donut ───────────────────────────────────────
with chart_col4:
    chart_header("Freight Composition by Industry", """
**B4 — Freight Composition by Industry**

Donut chart showing each industry group's share of total annual tonnes on this corridor.

The **centre value** is total annual tonnes across all industries.

A corridor dominated by a single industry (e.g. Agriculture > 80%) indicates a specialised freight flow. Diverse corridors suggest mixed urban or industrial demand patterns.

*Source: commodityreport endpoint · groupBy_l2=true*
""", section=False)
    if not records:
        st.info("No commodity data available.")
    else:
        donut_labels = [r.get("industry", "Unknown").capitalize() for r in records]
        donut_values = [r.get("tonnes", 0) for r in records]
        donut_colors = [_BLUE, _ORANGE, _GREEN, _PURPLE, _TEAL, _AMBER, _RED, _INDIGO]

        fig_donut = go.Figure(go.Pie(
            labels=donut_labels,
            values=donut_values,
            hole=0.45,
            marker_colors=donut_colors[:len(donut_labels)],
            hovertemplate="<b>%{label}</b><br>Tonnes: %{value:,.0f}<br>Share: %{percent}<extra></extra>",
            textinfo="label+percent",
            textfont_size=12,
        ))
        fig_donut.update_layout(
            **_PLOTLY_LAYOUT,
            showlegend=False,
            height=320,
            annotations=[dict(
                text=f"{totals['annual_tonnes']:,.0f} t",
                x=0.5, y=0.5,
                font_size=13,
                font_color="#374151",
                showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
st.divider()

# ---------------------------------------------------------------------------
# Navigation to Page 2
# ---------------------------------------------------------------------------

chart_header("OD Corridor Rankings", """
**OD Corridor Rankings — Page 2**

Navigate to Page 2 to compare this corridor against all other destinations from this origin.

- **Online API mode** — uses the densitymap endpoint; fast but numbers differ from Page 1
- **Local Data mode** — uses the downloaded commodityreport cache; consistent with Page 1 metrics
- **National mode** — requires local data to be downloaded for all states first
""")
st.markdown(
    '<div class="helper-text">'
    'See how this corridor compares to all other destinations from '
    f'<strong>{orig_name}</strong>. Rankings are available on the next page.'
    '</div>',
    unsafe_allow_html=True,
)
st.page_link("pages/Commodity_OD_Rankings.py", label="Go to Commodity OD Rankings →", icon="\U0001f52c")

st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Raw JSON expander
# ---------------------------------------------------------------------------

with st.expander("Raw JSON from API", expanded=False):
    st.code(json.dumps(records, indent=2), language="json")
