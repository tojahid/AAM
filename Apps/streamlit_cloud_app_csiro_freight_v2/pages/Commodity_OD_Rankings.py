"""
pages/commodity_detail_rankings.py  —  Commodity Detail Rankings (Page 4)

Like commodity_rankings.py (Page 3) but uses Level 3 individual commodity data
(groupBy_l2=false), exposing individual commodity names such as "Beer", "Milk",
"Aluminium Sulphate" rather than Level 2 industry groups.

Two-tier filter:
  1. Filter by Industry Group  (Level 2, optional — narrows commodity list)
  2. Filter by Commodity       (Level 3, primary filter — individual commodity names)

Local data stored in: api_local_data/level3/<STATE>/<LGA_CODE>.json

Run with:
    python -m streamlit run app_with_visualisation/app.py
"""

import json
import pathlib
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lga_codes import LGA_CODES, LGA_NAMES, LGA_STATE, SORTED_NAMES, STATE_COLORS, STATE_LGAS
from api import _compute_totals, fetch_origin_destinations, load_all_od_pairs, load_local_origin_data
from downloader import start_download_l3, cancel_download_l3, get_progress_l3

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Commodity Detail Rankings \u2014 FreightOD",
    page_icon="\U0001f52c",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS  (identical to commodity_rankings.py)
# ---------------------------------------------------------------------------

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #1E3A5F; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] div > small { color: #C8DAF0 !important; }
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio p,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [role="radiogroup"] label p,
[data-testid="stSidebar"] [role="radiogroup"] label span { color: #C8DAF0 !important; }
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSelectbox [data-testid="stWidgetLabel"] p {
    color: #A8C8E8 !important; font-size: 11px !important;
    text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600;
}
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stMultiSelect [data-testid="stWidgetLabel"] p {
    color: #A8C8E8 !important; font-size: 11px !important;
    text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600;
}
[data-testid="stSidebar"] [data-baseweb="select"] { border-radius: 6px !important; }
[data-testid="stSidebarContent"] hr { border-color: #2E5A8C !important; }
.section-label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: #9CA3AF; margin-bottom: 10px; margin-top: 4px;
}
.helper-text { font-size: 12px; color: #6B7280; margin-bottom: 12px; }
.state-badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; color: white; letter-spacing: 0.4px;
}
.lga-chip {
    display: inline-block; background: #F3F4F6; color: #374151;
    padding: 3px 10px; border-radius: 6px; font-family: monospace;
    font-size: 12px; font-weight: 600; border: 1px solid #E5E7EB;
}
.route-header { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 2px; }
.route-title { font-size: 24px; font-weight: 800; color: #111827; margin: 0; line-height: 1.2; }
.route-subtitle { color: #6B7280; font-size: 13px; margin-top: 4px; }
.rank-badge {
    display: inline-block; background: #FFF7ED; border: 2px solid #F97316;
    color: #C2410C; padding: 6px 16px; border-radius: 8px;
    font-size: 14px; font-weight: 700;
}
.main .block-container { padding-top: 1.5rem; }
[data-testid="stExpander"] { border: 1px solid #E5E7EB !important; border-radius: 8px !important; }
[data-testid="stPopover"] button {
    background: none !important; border: 1px solid #BFDBFE !important;
    color: #2563EB !important; font-size: 12px !important; padding: 2px 6px !important;
    font-weight: 700 !important; min-height: 0 !important; height: 26px !important;
    border-radius: 4px !important; box-shadow: none !important; line-height: 1 !important;
    margin-top: 1px !important;
}
[data-testid="stPopover"] button:hover {
    background: #EFF6FF !important; border-color: #93C5FD !important; color: #1D4ED8 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Level 3 data helpers
# ---------------------------------------------------------------------------

# Path to Level 3 local data (one level up from pages/)
LOCAL_DATA_ROOT_L3 = pathlib.Path(__file__).parent.parent / "api_local_data" / "level3"

# ---------------------------------------------------------------------------
# Predefined sector / industry commodity dicts
# ---------------------------------------------------------------------------

_SECTOR_DICT: dict[str, list[str]] = {
    "beverage":     ["liquor", "wine"],
    "cold_food":    ["box_beef", "box_chicken", "box_lamb", "box_pigs", "cheese",
                     "chicken", "butter", "cream_yoghurt", "fish", "prawn",
                     "salmon", "barramundi", "meat", "seafood"],
    "general":      ["clothes", "footwear", "tobacco"],
    "health":       ["pbs_medicines", "medicines", "technetium_99m", "hosp_medicines"],
    "horticulture": ["almonds", "blueberries", "cherries", "macadamias", "mushrooms",
                     "nectarines", "olives", "peaches", "strawberries", "apricots"],
}

_INDUSTRY_DICT: dict[str, list[str]] = {
    "alcohol_beverage": ["liquor", "wine"],
    "dairy_product":    ["cheese", "butter", "cream_yoghurt"],
    "fruit":            ["blueberries", "cherries", "nectarines", "olives", "peaches",
                         "strawberries", "apricots"],
    "household_general":["clothes", "footwear"],
    "meat":             ["box_beef", "box_chicken", "box_lamb", "box_pigs", "chicken", "meat"],
    "medicines":        ["pbs_medicines", "medicines", "technetium_99m", "hosp_medicines"],
    "nuts":             ["almonds", "macadamias"],
    "other_retail_ess": ["tobacco"],
    "seafood":          ["fish", "prawn", "salmon", "barramundi", "seafood"],
    "vegetables":       ["mushrooms"],
}

_COMMODITY_DISPLAY_OVERRIDES: dict[str, str] = {
    "pbs_medicines":  "PBS Medicines",
    "hosp_medicines": "Hospital Medicines",
    "technetium_99m": "Technetium-99m",
    "box_beef":       "Box Beef",
    "box_chicken":    "Box Chicken",
    "box_lamb":       "Box Lamb",
    "box_pigs":       "Box Pigs",
    "cream_yoghurt":  "Cream Yoghurt",
    "barramundi":     "Barramundi",
    "macadamias":     "Macadamias",
}


def _normalize(s: str) -> str:
    """Normalize commodity name for matching: 'Cream Yoghurt' → 'cream_yoghurt'"""
    return s.lower().replace(" ", "_")


def _fmt_commodity(s: str) -> str:
    """Display a commodity key: 'box_beef' → 'Box Beef'"""
    return _COMMODITY_DISPLAY_OVERRIDES.get(s, s.replace("_", " ").title())


def _fmt_sector(s: str) -> str:
    """Display a sector key: 'cold_food' → 'Cold Food'"""
    return s.replace("_", " ").title()


def _zero_totals() -> dict:
    """Return all-zero headline metrics for an OD pair with no matching records."""
    return {
        "annual_tonnes":            0.0,
        "annual_trailers":          0.0,
        "cost_per_tonne":           0.0,
        "total_transport_costs":    0.0,
        "total_freight_value":      0.0,
        "total_travel_distance_km": 0.0,
        "annual_tonne_km":          0.0,
        "avg_trip_distance_km":     0.0,
        "avg_trip_duration_hrs":    0.0,
        "total_co2_t":              0.0,
        "commodities_count":        0,
        "total_trips":              0,
    }


@st.cache_data(show_spinner=False)
def _get_l3_grouped() -> dict[str, list[str]]:
    """
    Scan up to 5 Level 3 JSON files per state directory and return
    {industry: [commodity_names]} mapping.  Sampling per-state ensures
    commodities from every state are discovered (not just ACT/NSW).
    Returns {} if no Level 3 data exists yet.
    """
    if not LOCAL_DATA_ROOT_L3.exists():
        return {}
    grouped: dict[str, set] = {}
    for state_dir in sorted(LOCAL_DATA_ROOT_L3.iterdir()):
        if not state_dir.is_dir():
            continue
        for json_file in list(sorted(state_dir.glob("*.json")))[:5]:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                for records in data.get("destinations", {}).values():
                    for r in records:
                        ind = r.get("industry")
                        com = r.get("commodity")
                        if ind and com:
                            grouped.setdefault(ind, set()).add(_normalize(com))
            except (OSError, json.JSONDecodeError):
                continue
    return {ind: sorted(comms) for ind, comms in sorted(grouped.items())}


# ---------------------------------------------------------------------------
# Filtered data loading functions (Level 3)
# ---------------------------------------------------------------------------

def _load_all_od_pairs_l3_filtered(
    industry_filter: frozenset | None,
    commodity_filter: frozenset | None,
) -> tuple[list[dict], str | None]:
    """
    Load all OD pairs from Level 3 local data, applying filters before aggregation.
    industry_filter: frozenset of Level 2 industry ids, or None (all)
    commodity_filter: frozenset of Level 3 commodity names, or None (all)
    """
    if not LOCAL_DATA_ROOT_L3.exists():
        return [], f"Level 3 local data not found: {LOCAL_DATA_ROOT_L3}"

    rows: list[dict] = []
    for state_dir in sorted(LOCAL_DATA_ROOT_L3.iterdir()):
        if not state_dir.is_dir():
            continue
        state = state_dir.name
        for json_file in sorted(state_dir.glob("*.json")):
            orig_lga = json_file.stem
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for dest_lga, records in data.get("destinations", {}).items():
                if not records:
                    continue
                filtered = records
                if industry_filter:
                    filtered = [r for r in filtered if r.get("industry") in industry_filter]
                if commodity_filter:
                    filtered = [r for r in filtered if _normalize(r.get("commodity", "")) in commodity_filter]
                t = (
                    _compute_totals(filtered, is_local=(orig_lga == dest_lga))
                    if filtered
                    else _zero_totals()
                )
                rows.append({
                    "orig_lga":       orig_lga,
                    "orig_state":     state,
                    "dest_lga":       dest_lga,
                    "tonnes":         t["annual_tonnes"],
                    "cost_per_tonne": t["cost_per_tonne"],
                    "transport_cost": t["total_transport_costs"],
                    "freight_value":  t["total_freight_value"],
                    "co2":            t["total_co2_t"],
                    "trips":          t["total_trips"],
                    "avg_distance":   t["avg_trip_distance_km"],
                })
    if not rows:
        return [], "No Level 3 local data found."
    return rows, None


def _load_local_origin_l3_filtered(
    orig_lga: str,
    orig_state: str,
    industry_filter: frozenset | None,
    commodity_filter: frozenset | None,
) -> tuple[dict | None, str | None]:
    """Load Level 3 local data for one origin, applying both filters before aggregation."""
    path = LOCAL_DATA_ROOT_L3 / orig_state / f"{orig_lga}.json"
    if not path.exists():
        return None, f"Level 3 local data not found at: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Failed to read Level 3 local file: {exc}"

    result: dict[str, dict] = {}
    for dest_lga, records in data.get("destinations", {}).items():
        if not records:
            continue
        filtered = records
        if industry_filter:
            filtered = [r for r in filtered if r.get("industry") in industry_filter]
        if commodity_filter:
            filtered = [r for r in filtered if _normalize(r.get("commodity", "")) in commodity_filter]
        result[dest_lga] = (
            _compute_totals(filtered, is_local=(orig_lga == dest_lga))
            if filtered
            else _zero_totals()
        )
    return result, None


@st.cache_data(show_spinner=False)
def _cached_od_pairs_l3(industry_filter_frozen: frozenset | None, commodity_filter_frozen: frozenset | None):
    return _load_all_od_pairs_l3_filtered(industry_filter_frozen, commodity_filter_frozen)


@st.cache_data(show_spinner=False)
def _cached_local_origin_l3(
    orig_lga: str, orig_state: str,
    industry_filter_frozen: frozenset | None, commodity_filter_frozen: frozenset | None,
):
    return _load_local_origin_l3_filtered(orig_lga, orig_state, industry_filter_frozen, commodity_filter_frozen)


@st.cache_data(show_spinner=False)
def _cached_origin_dests(orig_lga: str):
    return fetch_origin_destinations(orig_lga)


@st.cache_data(show_spinner=False)
def _cached_od_pairs_l2():
    return load_all_od_pairs()


@st.cache_data(show_spinner=False)
def _cached_local_origin_l2(orig_lga: str, orig_state: str):
    return load_local_origin_data(orig_lga, orig_state)


# ---------------------------------------------------------------------------
# Commodity summary loader — per-commodity aggregation (Filter Insights section)
# ---------------------------------------------------------------------------

def _load_commodity_summary_l3_filtered(
    industry_filter: frozenset | None,
    commodity_filter: frozenset | None,
    orig_lga: str | None = None,
    orig_state_arg: str | None = None,
) -> tuple[list[dict], str | None]:
    """
    Aggregate Level 3 local data PER COMMODITY NAME (not per OD pair).

    Unlike the existing filtered loaders which call _compute_totals() and lose
    the 'commodity' / 'industry' / 'sector' fields, this function accumulates
    raw record fields keyed by commodity name — yielding one summary row per
    distinct matched commodity.

    Parameters
    ----------
    industry_filter  : frozenset of industry keys, or None (all)
    commodity_filter : frozenset of normalised commodity keys, or None (all)
    orig_lga         : When provided, reads only that origin's JSON file (Single Origin).
                       When None, reads every file under LOCAL_DATA_ROOT_L3 (National).
    orig_state_arg   : Required when orig_lga is provided (e.g. "VIC").

    Returns
    -------
    (rows, error)
        rows  — list of dicts sorted by tonnes desc, each with keys:
                commodity_key, commodity_display, industry, sector,
                tonnes, transport_cost, cost_per_tonne, co2, trips, od_pairs
        error — str on fatal filesystem error, else None.
        Returns ([], None) when filter matches no records (not a fatal error).
    """
    if not LOCAL_DATA_ROOT_L3.exists():
        return [], f"Level 3 local data not found: {LOCAL_DATA_ROOT_L3}"

    # Determine which JSON files to scan
    if orig_lga is not None and orig_state_arg is not None:
        candidate = LOCAL_DATA_ROOT_L3 / orig_state_arg / f"{orig_lga}.json"
        if not candidate.exists():
            return [], f"Level 3 local data not found for {orig_lga} / {orig_state_arg}"
        json_files = [candidate]
    else:
        json_files = []
        for state_dir in sorted(LOCAL_DATA_ROOT_L3.iterdir()):
            if state_dir.is_dir():
                json_files.extend(sorted(state_dir.glob("*.json")))

    accum: dict[str, dict] = {}

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for dest_lga, records in data.get("destinations", {}).items():
            if not records:
                continue
            filtered = records
            if industry_filter:
                filtered = [r for r in filtered if r.get("industry") in industry_filter]
            if commodity_filter:
                filtered = [
                    r for r in filtered
                    if _normalize(r.get("commodity", "")) in commodity_filter
                ]
            for r in filtered:
                key = _normalize(r.get("commodity", "unknown"))
                if key not in accum:
                    accum[key] = {
                        "commodity_key":     key,
                        "commodity_display": _fmt_commodity(key),
                        "industry":          r.get("industry", ""),
                        "sector":            r.get("sector", ""),
                        "tonnes":            0.0,
                        "transport_cost":    0.0,
                        "freight_value":     0.0,
                        "co2":               0.0,
                        "trips":             0,
                        "od_pairs":          0,
                    }
                a = accum[key]
                a["tonnes"]         += r.get("tonnes", 0.0)
                a["transport_cost"] += r.get("trip_transport_costs", 0.0)
                a["freight_value"]  += r.get("total_freight_value", 0.0)
                a["co2"]            += r.get("co2_tn", 0.0)
                a["trips"]          += int(r.get("trips_count", 0))
                a["od_pairs"]       += 1

    if not accum:
        return [], None   # no match — not a filesystem error

    rows = sorted(accum.values(), key=lambda x: x["tonnes"], reverse=True)
    for row in rows:
        row["cost_per_tonne"] = (
            row["transport_cost"] / row["tonnes"] if row["tonnes"] > 0 else 0.0
        )
    return rows, None


@st.cache_data(show_spinner=False)
def _cached_commodity_summary(
    industry_filter_frozen: frozenset | None,
    commodity_filter_frozen: frozenset | None,
    orig_lga: str | None = None,
    orig_state_arg: str | None = None,
) -> tuple[list[dict], str | None]:
    """Cached wrapper for _load_commodity_summary_l3_filtered."""
    return _load_commodity_summary_l3_filtered(
        industry_filter_frozen,
        commodity_filter_frozen,
        orig_lga=orig_lga,
        orig_state_arg=orig_state_arg,
    )


# ---------------------------------------------------------------------------
# Commodity Filter Insights — corridor-level loader (per-commodity top-10 OD)
# ---------------------------------------------------------------------------

def _render_corridor_bar(corridors: list[dict], comm_key: str) -> None:
    """Render a Top-10 OD corridor horizontal bar chart for one commodity."""
    if not corridors:
        st.info(f"No corridor data for {_fmt_commodity(comm_key)}.", icon="ℹ️")
        return
    _labels = [f"{r['orig_name']} \u2192 {r['dest_name']}" for r in corridors]
    _colors = [STATE_COLORS.get(r["dest_state"], _BLUE) for r in corridors]
    fig = go.Figure(go.Bar(
        x=[r["tonnes"] for r in corridors],
        y=_labels,
        orientation="h",
        marker_color=_colors,
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Tonnes: %{x:,.0f}<br>"
            "Cost/Tonne: $%{customdata[0]:,.2f}<br>"
            "CO\u2082: %{customdata[1]:,.1f} t<extra></extra>"
        ),
        customdata=[[r["cost_per_tonne"], r["co2"]] for r in corridors],
    ))
    fig.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title="Annual Tonnes",
        yaxis=dict(autorange="reversed"),
        height=max(280, len(corridors) * 36 + 60),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    _seen_states = list(dict.fromkeys(r["dest_state"] for r in corridors))
    if _seen_states:
        _chips = " ".join(
            f'<span style="background:{STATE_COLORS.get(s, _BLUE)}; color:white; '
            f'padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600; '
            f'margin-right:3px;">{s}</span>'
            for s in _seen_states
        )
        st.markdown(
            f'<div style="margin-top:4px; line-height:2.2;">Destination state: {_chips}</div>',
            unsafe_allow_html=True,
        )


def _load_commodity_od_corridors_l3_filtered(
    industry_filter: frozenset | None,
    commodity_filter: frozenset | None,
    orig_lga: str | None = None,
    orig_state_arg: str | None = None,
) -> tuple[dict[str, list[dict]], str | None]:
    """
    Aggregate Level 3 local data per (commodity_key, orig_lga, dest_lga) triple.

    Returns {commodity_key: [top10 corridor dicts sorted by tonnes desc]}.

    Each corridor dict has:
        orig_lga, dest_lga, orig_name, dest_name, orig_state, dest_state,
        tonnes, transport_cost, cost_per_tonne, co2, trips
    """
    if not LOCAL_DATA_ROOT_L3.exists():
        return {}, f"Level 3 local data not found: {LOCAL_DATA_ROOT_L3}"

    if orig_lga is not None and orig_state_arg is not None:
        candidate = LOCAL_DATA_ROOT_L3 / orig_state_arg / f"{orig_lga}.json"
        if not candidate.exists():
            return {}, f"Level 3 local data not found for {orig_lga} / {orig_state_arg}"
        json_files = [candidate]
    else:
        json_files = []
        for state_dir in sorted(LOCAL_DATA_ROOT_L3.iterdir()):
            if state_dir.is_dir():
                json_files.extend(sorted(state_dir.glob("*.json")))

    # accum: {commodity_key: {(orig_lga, dest_lga): corridor_dict}}
    accum: dict[str, dict[tuple, dict]] = {}

    for jf in json_files:
        jf_orig = jf.stem
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for dest_lga_code, records in data.get("destinations", {}).items():
            if not records:
                continue
            filtered = records
            if industry_filter:
                filtered = [r for r in filtered if r.get("industry") in industry_filter]
            if commodity_filter:
                filtered = [
                    r for r in filtered
                    if _normalize(r.get("commodity", "")) in commodity_filter
                ]
            for r in filtered:
                key = _normalize(r.get("commodity", "unknown"))
                od_key = (jf_orig, dest_lga_code)
                if key not in accum:
                    accum[key] = {}
                if od_key not in accum[key]:
                    accum[key][od_key] = {
                        "orig_lga":   jf_orig,
                        "dest_lga":   dest_lga_code,
                        "tonnes":     0.0,
                        "transport_cost": 0.0,
                        "co2":        0.0,
                        "trips":      0,
                    }
                a = accum[key][od_key]
                a["tonnes"]         += r.get("tonnes", 0.0)
                a["transport_cost"] += r.get("trip_transport_costs", 0.0)
                a["co2"]            += r.get("co2_tn", 0.0)
                a["trips"]          += int(r.get("trips_count", 0))

    result: dict[str, list[dict]] = {}
    for comm_key, od_dict in accum.items():
        corridors = sorted(od_dict.values(), key=lambda x: x["tonnes"], reverse=True)
        for c in corridors:
            c["cost_per_tonne"] = c["transport_cost"] / c["tonnes"] if c["tonnes"] else 0.0
            c["orig_name"]  = LGA_CODES.get(c["orig_lga"], c["orig_lga"])
            c["dest_name"]  = LGA_CODES.get(c["dest_lga"], c["dest_lga"])
            c["orig_state"] = LGA_STATE.get(c["orig_lga"], "")
            c["dest_state"] = LGA_STATE.get(c["dest_lga"], "")
        result[comm_key] = corridors[:10]

    return result, None


@st.cache_data(show_spinner=False)
def _cached_commodity_od_corridors(
    industry_filter_frozen: frozenset | None,
    commodity_filter_frozen: frozenset | None,
    orig_lga: str | None = None,
    orig_state_arg: str | None = None,
) -> tuple[dict[str, list[dict]], str | None]:
    """Cached wrapper for _load_commodity_od_corridors_l3_filtered."""
    return _load_commodity_od_corridors_l3_filtered(
        industry_filter_frozen,
        commodity_filter_frozen,
        orig_lga=orig_lga,
        orig_state_arg=orig_state_arg,
    )


# ---------------------------------------------------------------------------
# Colour palette and Plotly layout
# ---------------------------------------------------------------------------

_BLUE   = "#2563EB"
_ORANGE = "#F97316"
_GREY   = "rgba(37,99,235,0.55)"

_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)

# ---------------------------------------------------------------------------
# Helper: chart header with info popover
# ---------------------------------------------------------------------------

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
        with st.popover("\u24d8"):
            st.markdown(info_md)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 16px 0;">
        <div style="font-size:22px; font-weight:800; color:white; letter-spacing:-0.3px;">
            🔬 Commodity Detail
        </div>
        <div style="font-size:13px; font-weight:600; color:#A8D4F5; margin-top:2px;">
            Individual Commodity Rankings
        </div>
        <div style="font-size:12px; color:#7BA7CC; margin-top:6px; line-height:1.5;">
            Filter by specific goods (Beer, Milk, Coal…)<br>
            CSIRO TraNSIT &middot; SIM-AU-BASELINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
<div style="background:linear-gradient(135deg,#2D1B4E,#5E35B1);
     border-left:4px solid #CE93D8; border-radius:6px;
     padding:10px 12px; margin:4px 0 12px 0;">
    <div style="font-size:10px; font-weight:700; color:#CE93D8;
         text-transform:uppercase; letter-spacing:0.8px; margin-bottom:4px;">
        🔬 Page 2 of 2
    </div>
    <div style="font-size:12px; color:#F3E5F5; line-height:1.5;">
        <strong>Commodity OD Rankings</strong><br>
        Rank corridors by individual commodity flows. Filter by commodity,
        sector, or industry group — nationally or for one origin.
    </div>
</div>
""", unsafe_allow_html=True)

    # ── SCOPE ──────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Scope</div>',
        unsafe_allow_html=True,
    )
    scope = st.radio(
        "Scope",
        options=["\U0001f30f All Origins \u2014 National", "\U0001f4cd Single Origin"],
        index=0,
        label_visibility="collapsed",
    )
    is_national = scope.startswith("\U0001f30f")

    st.divider()

    # ── ORIGIN (Single Origin scope only) ──────────────────────────────────
    orig_code = ""
    orig_name = ""
    orig_state_abbr = ""

    if not is_national:
        st.markdown(
            '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Origin LGA</div>',
            unsafe_allow_html=True,
        )
        orig_state_opts = ["All states"] + list(STATE_LGAS.keys())
        orig_state = st.selectbox(
            "Origin State",
            options=orig_state_opts,
            index=orig_state_opts.index("VIC") if "VIC" in orig_state_opts else 0,
            key="l3_orig_state",
            label_visibility="collapsed",
        )
        orig_lga_opts = SORTED_NAMES if orig_state == "All states" else STATE_LGAS[orig_state]

        if "l3_orig_lga_name" not in st.session_state:
            st.session_state["l3_orig_lga_name"] = orig_lga_opts[0]
        if st.session_state["l3_orig_lga_name"] not in orig_lga_opts:
            st.session_state["l3_orig_lga_name"] = orig_lga_opts[0]

        orig_name = st.selectbox(
            "Origin LGA",
            options=orig_lga_opts,
            index=orig_lga_opts.index(st.session_state["l3_orig_lga_name"]),
            label_visibility="collapsed",
        )
        st.session_state["l3_orig_lga_name"] = orig_name
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

    # ── STATE FILTER (National scope only) ────────────────────────────────
    state_filter: list[str] = []
    if is_national:
        st.markdown(
            '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Filter by Origin State</div>',
            unsafe_allow_html=True,
        )
        all_states = sorted(STATE_LGAS.keys())
        state_filter = st.multiselect(
            "Origin states",
            options=all_states,
            default=[],
            placeholder="All states",
            label_visibility="collapsed",
        )
        st.divider()

    # ── DATA SOURCE (Single Origin scope only) ────────────────────────────
    data_source = "\U0001f4be Local Data"
    if is_national:
        st.markdown(
            '<div style="font-size:11px; color:#7BA7CC; font-style:italic; margin-bottom:8px;">'
            'National view uses local data only.<br>Online API does not support multi-origin queries.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
            'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Data Source</div>',
            unsafe_allow_html=True,
        )
        data_source = st.radio(
            "Data source",
            options=["\U0001f4f6 Online (API)", "\U0001f4be Local Data"],
            index=0,
            label_visibility="collapsed",
        )
        st.divider()

    is_online = not is_national and "Online" in data_source

    # ── RANK BY ───────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Rank By</div>',
        unsafe_allow_html=True,
    )
    rank_metric = st.selectbox(
        "Rank by",
        options=["Tonnes", "Cost/Tonne (AUD)", "Transport Cost ($)", "CO\u2082 (t)", "Trips"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # ── COMMODITY FILTER ──────────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Commodity Filter</div>',
        unsafe_allow_html=True,
    )

    # Build grouped commodity data from L3 local files
    _l3_grouped = _get_l3_grouped()  # {industry: [normalized_commodity_keys]}
    _all_industries_l3 = sorted(_l3_grouped.keys())

    # ── Step 1: Filter category ──────────────────────────────────────────
    st.markdown(
        '<div style="font-size:10px; color:#7BA7CC; font-weight:600; '
        'text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Filter Category</div>',
        unsafe_allow_html=True,
    )
    filter_category_label = st.radio(
        "Filter category",
        options=["\U0001f4e1 TraNSIT API", "\u2699\ufe0f User-Defined Groups"],
        index=0,
        label_visibility="collapsed",
        disabled=is_online,
        key="l3_filter_category",
    )
    is_api_category = filter_category_label.startswith("\U0001f4e1")

    # ── Step 2: Sub-mode within selected category ────────────────────────
    st.markdown(
        '<div style="font-size:10px; color:#7BA7CC; font-weight:600; '
        'text-transform:uppercase; letter-spacing:0.5px; margin-top:8px; margin-bottom:4px;">'
        'Filter Type</div>',
        unsafe_allow_html=True,
    )

    if is_api_category:
        api_type_label = st.radio(
            "API filter type",
            options=["\U0001f310 All Commodities", "\U0001f3ed By Industry Group (L2)"],
            index=0,
            label_visibility="collapsed",
            disabled=is_online,
            key="l3_api_type",
        )
        filter_mode = "all" if api_type_label.startswith("\U0001f310") else "industry_group"
    else:
        user_type_label = st.radio(
            "User-defined filter type",
            options=["\U0001f4c2 By Sector", "\U0001f3f7\ufe0f By Industry"],
            index=0,
            label_visibility="collapsed",
            disabled=is_online,
            key="l3_user_type",
        )
        filter_mode = "sector" if user_type_label.startswith("\U0001f4c2") else "industry_dict"

    # ── Sub-controls depending on mode ──────────────────────────────────
    selected_groups:           list[str] = []
    selected_sectors:          list[str] = []
    selected_industries:       list[str] = []
    selected_all_commodities:  list[str] = []

    if is_online:
        st.markdown(
            '<div style="font-size:10px; color:#F59E0B; margin-top:6px; line-height:1.5;">'
            '\u26a0 Commodity filter requires <strong>Local Data</strong> mode.</div>',
            unsafe_allow_html=True,
        )
    elif filter_mode == "all":
        _all_commodities_sorted = sorted({c for comms in _l3_grouped.values() for c in comms})
        if _all_commodities_sorted:
            st.markdown(
                '<div style="font-size:10px; color:#A8C8E8; margin-top:6px; margin-bottom:4px;">'
                'Optional: select specific commodities</div>',
                unsafe_allow_html=True,
            )
            selected_all_commodities = st.multiselect(
                "Specific commodities",
                options=_all_commodities_sorted,
                format_func=_fmt_commodity,
                default=[],
                placeholder="Leave empty for all commodities",
                label_visibility="collapsed",
                key="l3_all_comm_sel",
            )
        else:
            st.markdown(
                '<div style="font-size:10px; color:#F59E0B; margin-top:4px;">'
                '\u26a0 No Level 3 data found. Download data first.</div>',
                unsafe_allow_html=True,
            )

    elif filter_mode == "industry_group":
        if _all_industries_l3:
            st.markdown(
                '<div style="font-size:10px; color:#A8C8E8; margin-top:6px; margin-bottom:4px;">'
                'Select industry groups</div>',
                unsafe_allow_html=True,
            )
            _ind_opts_display = [i.replace("_", " ").title() for i in _all_industries_l3]
            _sel_display = st.multiselect(
                "Industry groups",
                options=_ind_opts_display,
                default=[],
                placeholder="All industry groups",
                label_visibility="collapsed",
                key="l3_ind_group_sel",
            )
            _ind_display_to_key = {i.replace("_", " ").title(): i for i in _all_industries_l3}
            selected_groups = [_ind_display_to_key[d] for d in _sel_display if d in _ind_display_to_key]
        else:
            st.markdown(
                '<div style="font-size:10px; color:#F59E0B; margin-top:4px;">'
                '\u26a0 No Level 3 data found. Download data first.</div>',
                unsafe_allow_html=True,
            )

    elif filter_mode == "sector":
        st.markdown(
            '<div style="font-size:10px; color:#A8C8E8; margin-top:6px; margin-bottom:4px;">'
            'Select sectors</div>',
            unsafe_allow_html=True,
        )
        selected_sectors = st.multiselect(
            "Sectors",
            options=list(_SECTOR_DICT.keys()),
            default=[],
            format_func=_fmt_sector,
            placeholder="All sectors",
            label_visibility="collapsed",
            key="l3_sector_sel",
        )
        if selected_sectors:
            _sec_included = sorted({c for s in selected_sectors for c in _SECTOR_DICT[s]})
            st.markdown(
                '<div style="font-size:10px; color:#A8C8E8; margin-top:4px; line-height:1.6;">'
                '<strong>Includes:</strong> ' + ", ".join(_fmt_commodity(c) for c in _sec_included) +
                '</div>',
                unsafe_allow_html=True,
            )

    elif filter_mode == "industry_dict":
        st.markdown(
            '<div style="font-size:10px; color:#A8C8E8; margin-top:6px; margin-bottom:4px;">'
            'Select industry types</div>',
            unsafe_allow_html=True,
        )
        selected_industries = st.multiselect(
            "Industry types",
            options=list(_INDUSTRY_DICT.keys()),
            default=[],
            format_func=lambda x: x.replace("_", " ").title(),
            placeholder="All industry types",
            label_visibility="collapsed",
            key="l3_ind_dict_sel",
        )
        if selected_industries:
            _ind_included = sorted({c for ind in selected_industries for c in _INDUSTRY_DICT[ind]})
            st.markdown(
                '<div style="font-size:10px; color:#A8C8E8; margin-top:4px; line-height:1.6;">'
                '<strong>Includes:</strong> ' + ", ".join(_fmt_commodity(c) for c in _ind_included) +
                '</div>',
                unsafe_allow_html=True,
            )

    # ── Build filter frozensets ────────────────────────────────────────────
    industry_filter: frozenset | None = None
    commodity_filter: frozenset | None = None

    if not is_online:
        if filter_mode == "all" and selected_all_commodities:
            commodity_filter = frozenset(selected_all_commodities)
        elif filter_mode == "industry_group" and selected_groups:
            industry_filter = frozenset(selected_groups)
        elif filter_mode == "sector" and selected_sectors:
            commodity_filter = frozenset(c for s in selected_sectors for c in _SECTOR_DICT[s])
        elif filter_mode == "industry_dict" and selected_industries:
            commodity_filter = frozenset(c for ind in selected_industries for c in _INDUSTRY_DICT[ind])

    st.divider()

    # Footer
    if is_online:
        _filter_summary = "All commodities"
    elif filter_mode == "all":
        _filter_summary = (
            f"Commodities: {', '.join(_fmt_commodity(c) for c in sorted(commodity_filter))}"
            if commodity_filter else "All commodities"
        )
    elif filter_mode == "industry_group":
        _filter_summary = (
            f"Groups: {', '.join(g.replace('_',' ').title() for g in selected_groups)}"
            if selected_groups else "All industry groups"
        )
    elif filter_mode == "sector":
        _filter_summary = (
            f"Sectors: {', '.join(_fmt_sector(s) for s in selected_sectors)}"
            if selected_sectors else "All sectors"
        )
    else:
        _filter_summary = (
            f"Industries: {', '.join(i.replace('_',' ').title() for i in selected_industries)}"
            if selected_industries else "All industries"
        )

    st.markdown(
        '<div style="color:#5A8AB0; font-size:11px; line-height:1.7;">'
        'Commodity Detail Rankings<br>'
        'Dataset: SIM-AU-BASELINE<br>'
        f'Scope: {"National (all origins)" if is_national else "Single origin"}<br>'
        f'Source: {"Local L3 JSON cache" if is_national else ("\U0001f4f6 densitymap API" if is_online else "Local L3 JSON cache")}<br>'
        f'Filter: {_filter_summary}'
        '</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

if is_national:
    st.markdown("""
    <div class="route-header">
        <span class="route-title">Commodity Detail Rankings</span>
        <span style="font-size:14px; color:#9CA3AF; font-weight:400;">Level 3 individual commodities</span>
    </div>
    <div class="route-subtitle">
        Top freight corridors across all Australian LGAs &nbsp;&middot;&nbsp;
        SIM-AU-BASELINE &nbsp;&middot;&nbsp; Road &nbsp;&middot;&nbsp; Local Data (Level 3)
    </div>
    """, unsafe_allow_html=True)
else:
    orig_badge_color = STATE_COLORS.get(orig_state_abbr, "#4B5563")
    st.markdown(f"""
    <div class="route-header">
        <span class="route-title">{orig_name}</span>
        <span class="state-badge" style="background-color:{orig_badge_color};">{orig_state_abbr}</span>
        <span class="lga-chip">{orig_code}</span>
        <span style="font-size:22px; color:#9CA3AF; font-weight:300;">&#8594;</span>
        <span class="route-title" style="color:#9CA3AF;">All Destinations</span>
        <span style="font-size:14px; color:#9CA3AF; font-weight:400;">Commodity Detail</span>
    </div>
    <div class="route-subtitle">
        OD corridor rankings &nbsp;&middot;&nbsp; SIM-AU-BASELINE &nbsp;&middot;&nbsp; Road
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# Back links
col_back1, _ = st.columns([1, 6])
with col_back1:
    st.page_link("CSIRO_TraNSIT_Dashboard.py", label="\u2190 OD Metrics", icon="\U0001f69b")

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Download expander (Level 3)
# ---------------------------------------------------------------------------

with st.expander("\U0001f4e5 Update / Download Level 3 Local Data", expanded=False):
    st.caption(
        "Downloads individual commodity (Level 3) data to `api_local_data/level3/`. "
        "Files are ~15\u00d7 larger than Level 2 data (~600 MB total for all states)."
    )
    _prog = get_progress_l3()

    if _prog.running:
        _pct     = _prog.processed / _prog.total_lgas if _prog.total_lgas else 0
        _elapsed = time.time() - (_prog.start_time or time.time())
        _eta     = (_elapsed / _pct * (1 - _pct)) if _pct > 0.02 else None

        st.progress(
            _pct,
            text=(
                f"{_prog.processed} / {_prog.total_lgas} LGAs"
                + (f"  \u00b7  [{_prog.current_state}] {_prog.current_name}" if _prog.current_name else "")
            ),
        )
        _c1, _c2, _c3 = st.columns(3)
        _c1.metric("Elapsed", f"{int(_elapsed // 60)}m {int(_elapsed % 60)}s")
        _c2.metric("Est. remaining", f"{int(_eta // 60)}m {int(_eta % 60)}s" if _eta else "\u2026")
        _c3.metric("OD pairs saved", f"{_prog.total_pairs:,}")

        if _prog.log_lines:
            st.code("\n".join(_prog.log_lines[-8:]), language=None)
        if st.button("\u23f9 Cancel download", key="l3_cancel"):
            cancel_download_l3()
        time.sleep(2)
        st.rerun()

    elif _prog.done:
        if _prog.error:
            st.error(f"Download failed: {_prog.error}")
        elif _prog.cancelled:
            st.warning(
                f"Download cancelled. "
                f"{_prog.processed} LGAs processed, {_prog.total_pairs:,} OD pairs saved."
            )
        else:
            st.success(
                f"\u2705 Download complete!  "
                f"{_prog.processed} LGAs processed, {_prog.total_pairs:,} OD pairs saved. "
                f"({_prog.skipped} skipped \u2014 already cached)"
            )
        if st.button("Clear status", key="l3_clear"):
            _prog.reset()
            st.rerun()

    else:
        _dl_state_opts = ["All States"] + sorted(STATE_LGAS.keys())
        _dl_state = st.selectbox(
            "Download scope",
            options=_dl_state_opts,
            help="Select a single state for a faster partial download.",
            key="l3_dl_state",
        )
        _force = st.checkbox("Force re-download (overwrite already-cached files)", value=False, key="l3_force")
        _state_filter_dl = None if _dl_state == "All States" else _dl_state
        _n_lgas = (
            len(LGA_CODES) if _state_filter_dl is None
            else len(STATE_LGAS.get(_state_filter_dl, []))
        )
        _est_min = max(1, int(_n_lgas * 1.5))
        st.caption(
            f"**{_n_lgas} LGAs** \u2014 estimated time: ~{_est_min} min "
            f"({'all states' if _state_filter_dl is None else _state_filter_dl}). "
            "Existing files are skipped unless Force is checked."
        )
        if st.button("\u25b6 Start Download (Level 3)", type="primary", key="l3_start"):
            start_download_l3(state_filter=_state_filter_dl, force=_force)
            st.rerun()

st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Rank field mapping
# ---------------------------------------------------------------------------

_RANK_FIELD_MAP = {
    "Tonnes":              "tonnes",
    "Cost/Tonne (AUD)":   "cost_per_tonne",
    "Transport Cost ($)": "transport_cost",
    "CO\u2082 (t)":        "co2",
    "Trips":               "trips",
}
rank_field = _RANK_FIELD_MAP[rank_metric]

_RANK_LABEL_MAP = {
    "Tonnes":              ("Tonnes", ",.0f"),
    "Cost/Tonne (AUD)":   ("Cost/Tonne (AUD)", "$,.2f"),
    "Transport Cost ($)": ("Transport Cost ($)", "$,.0f"),
    "CO\u2082 (t)":        ("CO\u2082 (t)", ",.1f"),
    "Trips":               ("Trips", ",.0f"),
}
axis_label, fmt_str = _RANK_LABEL_MAP[rank_metric]

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

rows: list[dict] = []
data_note = ""

# ── National scope ──────────────────────────────────────────────────────────
if is_national:
    use_l2 = (industry_filter is None) and (commodity_filter is None)
    with st.spinner("Loading OD pairs from local data\u2026"):
        if use_l2:
            all_rows, data_error = _cached_od_pairs_l2()
        else:
            all_rows, data_error = _cached_od_pairs_l3(industry_filter, commodity_filter)

    if data_error or not all_rows:
        st.warning(
            "**No Level 3 local data found.**\n\n"
            "Use the **\U0001f4e5 Update / Download Level 3 Local Data** panel above to download.\n\n"
            "Select a state (e.g. VIC for a quick test) and click **\u25b6 Start Download (Level 3)**.",
            icon="\u26a0\ufe0f",
        )
        st.stop()

    if state_filter:
        all_rows = [r for r in all_rows if r["orig_state"] in state_filter]

    if not all_rows:
        st.info("No data for selected states.", icon="\u2139\ufe0f")
        st.stop()

    for r in all_rows:
        orig_n    = LGA_CODES.get(r["orig_lga"], r["orig_lga"])
        dest_n    = LGA_CODES.get(r["dest_lga"], r["dest_lga"])
        dest_state = LGA_STATE.get(r["dest_lga"], "")
        rows.append({
            "orig_lga":       r["orig_lga"],
            "orig_name":      orig_n,
            "orig_state":     r["orig_state"],
            "dest_lga":       r["dest_lga"],
            "dest_name":      dest_n,
            "dest_state":     dest_state,
            "tonnes":         r["tonnes"],
            "cost_per_tonne": r["cost_per_tonne"],
            "transport_cost": r["transport_cost"],
            "freight_value":  r["freight_value"],
            "co2":            r["co2"],
            "trips":          r["trips"],
            "avg_distance":   r["avg_distance"],
        })
    total_origins = len({r["orig_lga"] for r in rows})
    _data_level = (
        "Level 2 (complete freight \u2014 all industry groups)"
        if use_l2 else
        "Level 3 (filtered commodity flows)"
    )
    _l3_caveat = (
        "" if use_l2 else
        "  \u26a0\ufe0f Level 3 data is **partial**: individual commodity records are suppressed "
        "by the API when volumes are below a statistical disclosure threshold. "
        "Rankings reflect **identifiable commodity flows only** \u2014 not total freight."
    )
    data_note = (
        f"Loaded **{len(rows):,}** OD corridors from **{total_origins}** origins "
        f"({'selected states' if state_filter else 'all states'}) \u2014 {_data_level}.{_l3_caveat}"
    )

# ── Single Origin scope ─────────────────────────────────────────────────────
else:
    selected_dest_code = st.session_state.get("shared_dest_code", "")
    selected_dest_name = st.session_state.get("shared_dest_name", "")

    if is_online:
        # Online mode: no commodity filter available — uses densitymap (Level 2 only)
        st.warning(
            "\u26a0\ufe0f **Commodity filter unavailable in Online mode.** "
            "The densitymap API returns aggregated totals only \u2014 no individual commodity breakdown. "
            "Switch to **\U0001f4be Local Data** to use the commodity filter.",
            icon="\U0001f4e1",
        )
        with st.spinner(f"Loading all destinations from {orig_name}\u2026"):
            dest_records, data_error = _cached_origin_dests(orig_code)

        if data_error:
            st.error(f"**API Error:** {data_error}")
            st.stop()
        if not dest_records:
            st.info(
                f"No destinations found for **{orig_name}** via the API.",
                icon="\u2139\ufe0f",
            )
            st.stop()

        for r in dest_records:
            dlga   = r.get("dest_lga", "")
            dname  = r.get("name", LGA_CODES.get(dlga, dlga))
            dstate = LGA_STATE.get(dlga, "")
            rows.append({
                "orig_lga":       orig_code,
                "orig_name":      orig_name,
                "orig_state":     orig_state_abbr,
                "dest_lga":       dlga,
                "dest_name":      dname,
                "dest_state":     dstate,
                "tonnes":         r.get("tonnes", 0),
                "cost_per_tonne": r.get("cst_per_tonne", 0),
                "transport_cost": r.get("trip_transport_costs", 0),
                "freight_value":  r.get("total_freight_value", 0),
                "co2":            r.get("co2_tn", 0),
                "trips":          r.get("trips", 0),
                "avg_distance":   r.get("avg_trip_distance", 0),
            })
        data_note = (
            "Numbers from the **densitymap** endpoint \u2014 aggregated totals only, "
            "no individual commodity breakdown. Use **Local Data** for Level 3 filtering."
        )

    else:
        # Local Data mode: use L2 when no filter active (complete data), L3 when filtering
        use_l2 = (industry_filter is None) and (commodity_filter is None)
        if use_l2:
            local_dict, local_error = _cached_local_origin_l2(orig_code, orig_state_abbr)
            _no_data_msg = (
                f"**No local data found for {orig_name} ({orig_code}).**\n\n"
                "Use the **\U0001f4e5 Update / Download Local Data** panel above."
            )
            data_note = (
                "Numbers from the **Level 2 local commodityreport cache** \u2014 "
                "complete freight by industry group (groupBy_l2=true)."
            )
        else:
            local_dict, local_error = _cached_local_origin_l3(
                orig_code, orig_state_abbr, industry_filter, commodity_filter
            )
            _no_data_msg = (
                f"**No Level 3 local data found for {orig_name} ({orig_code}).**\n\n"
                "Use the **\U0001f4e5 Update / Download Level 3 Local Data** panel above, "
                "or switch to **\U0001f4f6 Online (API)**."
            )
            data_note = (
                "Numbers from the **Level 3 local commodityreport cache** \u2014 "
                "individual commodity records (groupBy_l2=false).  "
                "\u26a0\ufe0f Partial data: suppressed commodities excluded."
            )
        if local_dict is None:
            st.warning(_no_data_msg, icon="\u26a0\ufe0f")
            st.stop()

        for dest_lga, totals in local_dict.items():
            dname  = LGA_CODES.get(dest_lga, dest_lga)
            dstate = LGA_STATE.get(dest_lga, "")
            rows.append({
                "orig_lga":       orig_code,
                "orig_name":      orig_name,
                "orig_state":     orig_state_abbr,
                "dest_lga":       dest_lga,
                "dest_name":      dname,
                "dest_state":     dstate,
                "tonnes":         totals.get("annual_tonnes", 0),
                "cost_per_tonne": totals.get("cost_per_tonne", 0),
                "transport_cost": totals.get("total_transport_costs", 0),
                "freight_value":  totals.get("total_freight_value", 0),
                "co2":            totals.get("total_co2_t", 0),
                "trips":          totals.get("total_trips", 0),
                "avg_distance":   totals.get("avg_trip_distance_km", 0),
            })

if not rows:
    st.info("No destination data available.", icon="\u2139\ufe0f")
    st.stop()

st.info(data_note, icon="\u2139\ufe0f")

# ── Active filter indicator ───────────────────────────────────────────────
if (industry_filter or commodity_filter) and not is_online:
    if filter_mode == "all" and commodity_filter:
        _c_list = ", ".join(_fmt_commodity(c) for c in sorted(commodity_filter))
        _banner_label = f"Specific commodities: **{_c_list}**"
    elif filter_mode == "industry_group" and industry_filter:
        _banner_label = (
            f"Industry groups: **{', '.join(sorted(i.replace('_',' ').title() for i in industry_filter))}**"
        )
    elif filter_mode == "sector" and commodity_filter:
        _s_names = ", ".join(_fmt_sector(s) for s in selected_sectors)
        _c_list  = ", ".join(_fmt_commodity(c) for c in sorted(commodity_filter))
        _banner_label = f"Sectors: **{_s_names}** → includes: {_c_list}"
    elif filter_mode == "industry_dict" and commodity_filter:
        _i_names = ", ".join(i.replace("_", " ").title() for i in selected_industries)
        _c_list  = ", ".join(_fmt_commodity(c) for c in sorted(commodity_filter))
        _banner_label = f"Industries: **{_i_names}** → includes: {_c_list}"
    else:
        _banner_label = ""
    if _banner_label:
        st.info(
            f"\U0001f52c **Level 3 filter active:** {_banner_label}. "
            "Metrics reflect selected types only. "
            "Corridors with no data for the selected commodity show zero and appear at the bottom.",
        icon="\U0001f50d",
    )

# ---------------------------------------------------------------------------
# Commodity Filter Insights — per-commodity breakdown (filter active only)
# ---------------------------------------------------------------------------

if (industry_filter or commodity_filter) and not is_online:
    st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
    st.divider()

    chart_header("Commodity Filter Insights", """
**Commodity Filter Insights**

This section appears only when a **Commodity Filter** is active in the sidebar.
It breaks down the filtered result set by individual commodity, revealing which
specific goods make up the group — e.g. if *Cold Food* is selected, this shows
whether Beef, Chicken, Fish or Lamb dominates by volume.

| Card | Meaning |
|---|---|
| Commodities Matched | Number of distinct commodity types found in the filter |
| Total Tonnes | SUM of annual tonnes across all OD corridors in the current scope |
| Avg Cost / Tonne | Weighted average: `SUM(transport_cost) / SUM(tonnes)` |
| Total CO₂ | SUM of annual CO₂ emissions (tonnes) across all corridors |

> **Scope:** National view reads all downloaded origin LGAs. Single Origin reads only
> the selected origin's data — faster but limited to that origin's freight flows.

> **Suppression caveat:** CSIRO statistically suppresses flows with fewer than ~5
> movements per commodity. Totals may undercount the true national figure.
""")

    with st.spinner("Loading commodity breakdown…"):
        if is_national:
            _comm_rows, _comm_err = _cached_commodity_summary(
                industry_filter, commodity_filter,
                orig_lga=None, orig_state_arg=None,
            )
        else:
            _comm_rows, _comm_err = _cached_commodity_summary(
                industry_filter, commodity_filter,
                orig_lga=orig_code, orig_state_arg=orig_state_abbr,
            )

    if _comm_err:
        st.warning(f"Could not load commodity breakdown: {_comm_err}")
    elif not _comm_rows:
        st.info(
            "No commodity records matched the current filter. "
            "Try broadening the selection or switching to a different origin.",
            icon="ℹ️",
        )
    else:
        # ── Summary metric cards ─────────────────────────────────────────────
        _ci_total_commodities = len(_comm_rows)
        _ci_total_tonnes      = sum(r["tonnes"] for r in _comm_rows)
        _ci_total_cost        = sum(r["transport_cost"] for r in _comm_rows)
        _ci_total_co2         = sum(r["co2"] for r in _comm_rows)
        _ci_avg_cpt           = _ci_total_cost / _ci_total_tonnes if _ci_total_tonnes else 0.0

        def _fmt_ci_tonnes(v: float) -> str:
            if v >= 1_000_000:
                return f"{v / 1_000_000:.2f}M t"
            if v >= 1_000:
                return f"{v / 1_000:.1f}K t"
            return f"{v:,.0f} t"

        _ci_m1, _ci_m2, _ci_m3, _ci_m4 = st.columns(4)
        with _ci_m1:
            st.metric("Commodities Matched", f"{_ci_total_commodities}")
        with _ci_m2:
            st.metric("Total Tonnes", _fmt_ci_tonnes(_ci_total_tonnes))
        with _ci_m3:
            st.metric("Avg Cost / Tonne", f"${_ci_avg_cpt:,.2f}")
        with _ci_m4:
            st.metric("Total CO\u2082", _fmt_ci_tonnes(_ci_total_co2))

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

        # ── Industry colour map ──────────────────────────────────────────────
        _INDUSTRY_COLORS: dict[str, str] = {
            "food":              "#10B981",
            "livestock":         "#F97316",
            "vehicles":          "#4F46E5",
            "waste":             "#9CA3AF",
            "horticulture":      "#34D399",
            "wood_product":      "#92400E",
            "beverage":          "#2563EB",
            "alcohol_beverage":  "#1D4ED8",
            "medicines":         "#DC2626",
            "fuel":              "#D97706",
            "grains":            "#A16207",
            "meat":              "#EF4444",
            "dairy_product":     "#0EA5E9",
            "seafood":           "#0D9488",
            "fruit":             "#F59E0B",
            "vegetables":        "#16A34A",
            "chemicals":         "#6B7280",
            "fibre":             "#A3E635",
            "sugar":             "#FCD34D",
            "viticulture":       "#7C3AED",
            "nuts":              "#78350F",
            "tissue_product":    "#BAE6FD",
            "ppe":               "#E879F9",
            "household_general": "#6B7280",
            "other_retail_ess":  "#9CA3AF",
        }

        # ── Chart columns ────────────────────────────────────────────────────
        _ci_col_a, _ci_col_b = st.columns(2)

        # ── Chart A — Commodity Share by Tonnes ──────────────────────────────
        with _ci_col_a:
            chart_header("Commodity Share by Tonnes", """
**Commodity Share by Tonnes**

Each horizontal bar represents one commodity, sorted from highest to lowest
annual tonnage. Bar colour indicates the **industry group** (e.g. food, livestock,
grains) as classified in the CSIRO TraNSIT dataset.

- Values are **annual totals** summed across all OD corridors in the current scope
- Hover to see **tonnes** and **weighted average cost per tonne** for each commodity
- Maximum **20 commodities** shown; if the filter returns more, the lowest-volume
  ones are omitted from this chart but still appear in the full rankings table below

> **Colour key:** See the industry label chips below the chart.
""", section=False)

            _ci_top20 = _comm_rows[:20]
            _ci_bar_colors = [
                _INDUSTRY_COLORS.get(r["industry"], _BLUE) for r in _ci_top20
            ]
            fig_ci_a = go.Figure(go.Bar(
                x=[r["tonnes"] for r in _ci_top20],
                y=[r["commodity_display"] for r in _ci_top20],
                orientation="h",
                marker_color=_ci_bar_colors,
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Tonnes: %{x:,.0f}<br>"
                    "Cost/Tonne: $%{customdata[0]:,.2f}<extra></extra>"
                ),
                customdata=[[r["cost_per_tonne"]] for r in _ci_top20],
            ))
            fig_ci_a.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis_title="Annual Tonnes",
                yaxis=dict(autorange="reversed"),
                height=max(300, len(_ci_top20) * 26 + 60),
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig_ci_a, use_container_width=True)

            # Inline industry colour legend chips
            _seen_industries: list[str] = []
            _seen_set: set[str] = set()
            for _r in _ci_top20:
                _ind = _r["industry"]
                if _ind and _ind not in _seen_set:
                    _seen_industries.append(_ind)
                    _seen_set.add(_ind)
            if _seen_industries:
                _legend_chips = " ".join(
                    f'<span style="background:{_INDUSTRY_COLORS.get(i, _BLUE)}; '
                    f'color:white; padding:2px 8px; border-radius:3px; '
                    f'font-size:10px; font-weight:600; margin-right:3px;">'
                    f'{i.replace("_", " ").title()}</span>'
                    for i in _seen_industries
                )
                st.markdown(
                    f'<div style="margin-top:4px; line-height:2.2;">{_legend_chips}</div>',
                    unsafe_allow_html=True,
                )

        # ── Chart B — Cost vs Volume scatter ─────────────────────────────────
        with _ci_col_b:
            chart_header("Cost vs Volume by Commodity", """
**Cost vs Volume by Commodity**

Each dot represents one matched commodity. Position reveals the trade-off between
scale and cost efficiency across the filtered group.

| Axis / Property | Meaning |
|---|---|
| **X-axis** | Total annual tonnes (volume proxy) |
| **Y-axis** | Weighted avg cost per tonne — `SUM(transport_cost) / SUM(tonnes)` |
| **Dot size** | Proportional to total CO₂ emissions (min 8 px, max 40 px) |
| **Dot colour** | Industry group (same palette as Chart A) |

**Quadrant interpretation:**
- **Top-left** — expensive, low-volume (specialised or long-haul goods)
- **Top-right** — expensive, high-volume (premium bulk freight)
- **Bottom-left** — cheap, low-volume (minor local flows)
- **Bottom-right** — cost-efficient, high-volume (bulk commodities)

> Requires at least **2 matched commodities** to render.
> Hover over any dot for full metrics.
""", section=False)

            if len(_comm_rows) < 2:
                st.info(
                    "Scatter plot requires at least 2 matched commodities. "
                    "Only 1 commodity matched the current filter.",
                    icon="ℹ️",
                )
            else:
                _ci_max_co2 = max(r["co2"] for r in _comm_rows) or 1.0
                _ci_sizes = [
                    max(8.0, min(40.0, r["co2"] / _ci_max_co2 * 40.0))
                    for r in _comm_rows
                ]
                _ci_sc_colors = [
                    _INDUSTRY_COLORS.get(r["industry"], _BLUE) for r in _comm_rows
                ]
                fig_ci_b = go.Figure(go.Scatter(
                    x=[r["tonnes"] for r in _comm_rows],
                    y=[r["cost_per_tonne"] for r in _comm_rows],
                    mode="markers+text",
                    text=[r["commodity_display"] for r in _comm_rows],
                    textposition="top center",
                    textfont=dict(size=9, color="#374151"),
                    marker=dict(
                        color=_ci_sc_colors,
                        size=_ci_sizes,
                        line=dict(width=1, color="white"),
                        opacity=0.85,
                    ),
                    hovertemplate=(
                        "<b>%{text}</b><br>"
                        "Tonnes: %{x:,.0f}<br>"
                        "Cost/Tonne: $%{y:,.2f}<br>"
                        "CO\u2082: %{customdata[0]:,.1f} t<br>"
                        "Trips: %{customdata[1]:,}<extra></extra>"
                    ),
                    customdata=[[r["co2"], r["trips"]] for r in _comm_rows],
                ))
                fig_ci_b.update_layout(
                    **_PLOTLY_LAYOUT,
                    xaxis_title="Annual Tonnes",
                    yaxis_title="Avg Cost per Tonne (AUD/t)",
                    height=max(300, len(_ci_top20) * 26 + 60),
                    margin=dict(l=10, r=10, t=10, b=40),
                    showlegend=False,
                )
                st.plotly_chart(fig_ci_b, use_container_width=True)
                st.caption(
                    "Dot size \u221d CO\u2082 emissions \u00b7 "
                    "Coloured by industry group \u00b7 "
                    "Hover for full metrics"
                )

        # ── Chart 1 — Multi-Metric Commodity Comparison Table ────────────────
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        chart_header("Multi-Metric Commodity Comparison", """
**Multi-Metric Commodity Comparison**

Each row = one matched commodity. Columns show all key freight metrics side by side,
making it easy to compare performance across commodities in the current filter group.

| Column | Formula / Meaning |
|---|---|
| **Tonnes** | SUM of annual tonnes across all OD corridors in scope |
| **Cost/Tonne ($)** | SUM(transport\\_cost) / SUM(tonnes) — weighted average |
| **CO\u2082/Tonne (kg)** | SUM(co2) / SUM(tonnes) \u00d7 1000 — carbon intensity |
| **Load Factor (t/trip)** | SUM(tonnes) / SUM(trips) — trailer utilisation proxy |
| **OD Pairs** | Number of distinct origin\u2192destination corridors carrying this commodity |
| **Total CO\u2082 (t)** | SUM of annual CO\u2082 across all OD corridors in scope |

> **TOTAL row** shows column sums or weighted averages where appropriate.
> Download the table as CSV using the button below.
""", section=False)

        _ci_df_rows = [
            {
                "Commodity":             r["commodity_display"],
                "Industry":              r["industry"].replace("_", " ").title() if r["industry"] else "",
                "Tonnes":                r["tonnes"],
                "Cost/Tonne ($)":        r["cost_per_tonne"],
                "CO\u2082/Tonne (kg)":   r["co2"] / r["tonnes"] * 1000 if r["tonnes"] else 0.0,
                "Load Factor (t/trip)":  r["tonnes"] / r["trips"] if r["trips"] else 0.0,
                "OD Pairs":              r["od_pairs"],
                "Total CO\u2082 (t)":    r["co2"],
            }
            for r in _comm_rows
        ]
        _ci_total_trips = sum(r["trips"] for r in _comm_rows)
        _ci_df_rows.append({
            "Commodity":             "TOTAL / WEIGHTED AVG",
            "Industry":              "",
            "Tonnes":                _ci_total_tonnes,
            "Cost/Tonne ($)":        _ci_total_cost / _ci_total_tonnes if _ci_total_tonnes else 0.0,
            "CO\u2082/Tonne (kg)":   _ci_total_co2 / _ci_total_tonnes * 1000 if _ci_total_tonnes else 0.0,
            "Load Factor (t/trip)":  _ci_total_tonnes / _ci_total_trips if _ci_total_trips else 0.0,
            "OD Pairs":              sum(r["od_pairs"] for r in _comm_rows),
            "Total CO\u2082 (t)":    _ci_total_co2,
        })
        _ci_display_df = pd.DataFrame(_ci_df_rows)
        st.dataframe(
            _ci_display_df.style.format({
                "Tonnes":               "{:,.0f}",
                "Cost/Tonne ($)":       "${:,.2f}",
                "CO\u2082/Tonne (kg)":  "{:,.2f}",
                "Load Factor (t/trip)": "{:,.2f}",
                "OD Pairs":             "{:,}",
                "Total CO\u2082 (t)":   "{:,.1f}",
            }),
            use_container_width=True,
            hide_index=True,
        )
        _ci_csv = _ci_display_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "\u2b07\ufe0f Download Comparison Table (CSV)",
            data=_ci_csv,
            file_name="commodity_comparison.csv",
            mime="text/csv",
            key="dl_commodity_comparison",
        )

        # ── Chart 2 — Freight Value-to-Cost Ratio ────────────────────────────
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        chart_header("Freight Value-to-Cost Ratio", """
**Freight Value-to-Cost Ratio**

Each bar shows the **economic return per dollar of transport cost** for one commodity:

> **Ratio = Total Freight Value \u00f7 Total Transport Cost**

- **High ratio (green)** \u2014 freight is high-value relative to its transport cost;
  every dollar of logistics moves valuable goods (e.g. medicines, premium food)
- **Low ratio (amber)** \u2014 bulk or lower-margin commodity where transport is a
  larger share of total declared value (e.g. waste, low-grade grain)
- **Ratio < 1** \u2014 transport cost exceeds declared freight value (suppressed flows
  or data artefacts \u2014 treat with caution)

Bars sorted highest to lowest. Hover to see absolute freight value and transport cost.
""", section=False)

        _ci_vcr = [
            {**r, "value_cost_ratio": r.get("freight_value", 0.0) / r["transport_cost"]
             if r["transport_cost"] > 0 else 0.0}
            for r in _comm_rows
        ]
        _ci_vcr.sort(key=lambda x: x["value_cost_ratio"], reverse=True)
        _ci_vcr_max = max(r["value_cost_ratio"] for r in _ci_vcr) or 1.0

        def _vcr_color(ratio: float, max_r: float) -> str:
            """Interpolate amber(217,119,6) \u2192 green(16,185,129) by ratio fraction."""
            t = min(1.0, ratio / max_r)
            return (
                f"rgba({int(217 - 201 * t)},"
                f"{int(119 + 66  * t)},"
                f"{int(6   + 123 * t)},0.85)"
            )

        _ci_vcr_colors = [_vcr_color(r["value_cost_ratio"], _ci_vcr_max) for r in _ci_vcr]

        fig_vcr = go.Figure(go.Bar(
            x=[r["value_cost_ratio"] for r in _ci_vcr],
            y=[r["commodity_display"] for r in _ci_vcr],
            orientation="h",
            marker_color=_ci_vcr_colors,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Value / Cost Ratio: %{x:.2f}\u00d7<br>"
                "Freight Value: $%{customdata[0]:,.0f}<br>"
                "Transport Cost: $%{customdata[1]:,.0f}<extra></extra>"
            ),
            customdata=[[r.get("freight_value", 0.0), r["transport_cost"]] for r in _ci_vcr],
        ))
        fig_vcr.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Freight Value / Transport Cost (\u00d7)",
            yaxis=dict(autorange="reversed"),
            height=max(300, len(_ci_vcr) * 26 + 60),
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_vcr, use_container_width=True)
        st.caption(
            "Green = high-value freight \u00b7 Amber = lower-margin / bulk freight \u00b7 "
            "Hover for absolute freight value and transport cost"
        )

        # ── Chart 3 — Top 10 OD Corridors per Commodity (tabbed) ─────────────
        st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
        chart_header("Top 10 OD Corridors by Commodity", """
**Top 10 OD Corridors by Commodity**

Each tab (or dropdown) shows the **top 10 freight corridors** for one matched commodity,
sorted by annual tonnes.

- Each bar = one origin \u2192 destination LGA pair
- **Bar colour** = destination state (same palette as state-level charts)
- **Hover** to see tonnes, cost per tonne, and CO\u2082

> Corridors with fewer than \u223c5 movements per commodity are suppressed by CSIRO
> and will not appear here. National view covers all downloaded origin LGAs.
""", section=False)

        with st.spinner("Loading top OD corridors\u2026"):
            if is_national:
                _corr_data, _corr_err = _cached_commodity_od_corridors(
                    industry_filter, commodity_filter,
                    orig_lga=None, orig_state_arg=None,
                )
            else:
                _corr_data, _corr_err = _cached_commodity_od_corridors(
                    industry_filter, commodity_filter,
                    orig_lga=orig_code, orig_state_arg=orig_state_abbr,
                )

        if _corr_err:
            st.warning(f"Could not load corridor data: {_corr_err}")
        elif not _corr_data:
            st.info("No corridor data matched the current filter.", icon="\u2139\ufe0f")
        else:
            _corr_keys   = [r["commodity_key"] for r in _comm_rows if r["commodity_key"] in _corr_data]
            _corr_labels = [_fmt_commodity(k) for k in _corr_keys]

            if len(_corr_keys) <= 8:
                _corr_tabs = st.tabs(_corr_labels)
                for _ctab, _ck in zip(_corr_tabs, _corr_keys):
                    with _ctab:
                        _render_corridor_bar(_corr_data[_ck], _ck)
            else:
                _sel_label = st.selectbox(
                    "Select commodity to view top corridors:",
                    options=_corr_labels,
                    key="comm_corr_select",
                )
                _sel_key = _corr_keys[_corr_labels.index(_sel_label)]
                _render_corridor_bar(_corr_data[_sel_key], _sel_key)

    st.divider()

# ---------------------------------------------------------------------------
# Sort + rank
# ---------------------------------------------------------------------------

df = pd.DataFrame(rows)
df = df.sort_values(rank_field, ascending=False).reset_index(drop=True)
df.insert(0, "Rank", range(1, len(df) + 1))

total_count = len(df)

selected_dest_code = "" if is_national else st.session_state.get("shared_dest_code", "")
selected_dest_name = "" if is_national else st.session_state.get("shared_dest_name", "")
selected_rank = None
if selected_dest_code and not is_national:
    sel_rows = df[df["dest_lga"] == selected_dest_code]
    if not sel_rows.empty:
        selected_rank = int(sel_rows.iloc[0]["Rank"])

if selected_rank is not None:
    rank_col, _ = st.columns([2, 6])
    with rank_col:
        st.markdown(
            f'<div class="rank-badge">'
            f'\U0001f4cd {selected_dest_name or selected_dest_code} &nbsp; '
            f'<strong>#{selected_rank}</strong> of {total_count} &nbsp;'
            f'by {rank_metric}'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helper: bar colour (single origin only)
# ---------------------------------------------------------------------------

def bar_colors(dest_lgas: list[str]) -> list[str]:
    if not selected_dest_code:
        return [_BLUE] * len(dest_lgas)
    return [_ORANGE if d == selected_dest_code else _BLUE for d in dest_lgas]

# ===========================================================================
# NATIONAL-ONLY: B1 – B5 summary charts
# ===========================================================================

if is_national:

    # ── B1 — National Summary Cards ──────────────────────────────────────
    chart_header("National Summary", """
**National Summary Cards**

Aggregated totals across all OD corridors loaded from the Level 3 local data cache.

Values update when you apply **State**, **Industry Group**, or **Commodity** filters.

> **Median Cost/Tonne** is the unweighted median across all corridors (each corridor counted equally regardless of freight volume).

> **Tip:** Use the Download panel above to fetch Level 3 data for a state before ranking.
""")

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    with sc1:
        st.metric("OD Corridors", f"{total_count:,}")
    with sc2:
        st.metric("Total Tonnes", f"{df['tonnes'].sum():,.0f} t")
    with sc3:
        st.metric("Median Cost/Tonne", f"${df['cost_per_tonne'].median():,.2f}")
    with sc4:
        st.metric("Total CO\u2082", f"{df['co2'].sum():,.1f} t")
    with sc5:
        st.metric("Origins with Data", f"{df['orig_lga'].nunique()}")

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── B2 — State-to-State Flow Heatmap ─────────────────────────────────
    chart_header("State-to-State Freight Flows", """
**State-to-State Flow Heatmap**

Each cell shows total annual tonnes from an **origin state** (rows) to a **destination state** (columns).

- **Diagonal** = intra-state freight
- **Darker** = higher volume
- Responds to all active filters (state, industry group, commodity)
""")

    _state_flow = df.groupby(["orig_state", "dest_state"])["tonnes"].sum().reset_index()
    _states_hm = sorted(set(_state_flow["orig_state"].tolist() + _state_flow["dest_state"].tolist()))
    _matrix = pd.DataFrame(0.0, index=_states_hm, columns=_states_hm)
    for _, _r in _state_flow.iterrows():
        if _r["orig_state"] in _matrix.index and _r["dest_state"] in _matrix.columns:
            _matrix.loc[_r["orig_state"], _r["dest_state"]] = _r["tonnes"]

    _text_matrix = [[f"{v:,.0f} t" if v > 0 else "" for v in row] for row in _matrix.values]

    fig_hm = go.Figure(go.Heatmap(
        z=_matrix.values, x=_states_hm, y=_states_hm,
        text=_text_matrix, texttemplate="%{text}", textfont=dict(size=11),
        colorscale="Blues", hoverongaps=False,
        hovertemplate="<b>%{y} \u2192 %{x}</b><br>Tonnes: %{z:,.0f}<extra></extra>",
        colorbar=dict(title="Tonnes", tickformat=",.0f"),
    ))
    fig_hm.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title="Destination State", yaxis_title="Origin State",
        height=max(320, len(_states_hm) * 55),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("Diagonal = intra-state freight. Off-diagonal = inter-state freight.")

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── R1 — Top 20 National OD Corridors ────────────────────────────────
    chart_header("Top 20 National OD Corridors", """
**Top 20 National OD Corridors**

The 20 highest-ranked freight corridors sorted by the selected **Rank By** metric.

- **Rank 1 = highest value.** For **Cost/Tonne** this means the most expensive corridor.
- Bars coloured by **origin state**
- Values reflect the selected commodity filter only

Change the metric using the **Rank By** selector in the sidebar.
""")

    _topN_nat = df.head(20)
    _topN_nat_colors = [STATE_COLORS.get(s, "#4B5563") for s in _topN_nat["orig_state"]]
    _y_labels_nat = [
        f"#{r} {on} \u2192 {dn}"
        for r, on, dn in zip(_topN_nat["Rank"], _topN_nat["orig_name"], _topN_nat["dest_name"])
    ]
    _fig_r1_nat = go.Figure(go.Bar(
        x=_topN_nat[rank_field].tolist(),
        y=_y_labels_nat,
        orientation="h",
        marker_color=_topN_nat_colors,
        hovertemplate=(
            "<b>%{y}</b><br>"
            f"{axis_label}: %{{x:{fmt_str}}}<br>"
            "Tonnes: %{customdata[0]:,.0f}<br>"
            "Cost/t: $%{customdata[1]:,.2f}<br>"
            "CO\u2082: %{customdata[2]:,.1f} t<extra></extra>"
        ),
        customdata=_topN_nat[["tonnes", "cost_per_tonne", "co2"]].values.tolist(),
    ))
    _fig_r1_nat.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title=axis_label, yaxis_autorange="reversed",
        height=500, margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(_fig_r1_nat, use_container_width=True)

    _states_in_top_nat = sorted(_topN_nat["orig_state"].unique())
    _legend_html_nat = " ".join([
        f'<span style="background:{STATE_COLORS.get(s, "#4B5563")}; color:white; '
        f'padding:2px 8px; border-radius:3px; font-size:11px; font-weight:600; '
        f'margin-right:4px;">{s}</span>'
        for s in _states_in_top_nat
    ])
    st.markdown(f'<div style="margin-top:4px; margin-bottom:8px;">{_legend_html_nat}</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── B3 — Top Origins / Top Destinations ──────────────────────────────
    chart_header("Top Origins & Top Destinations", """
**Top Origins & Top Destinations**

**Left** — Top 10 origin LGAs by total outbound tonnes. **Right** — Top 10 destination LGAs by total inbound tonnes.

Both charts reflect the active commodity and industry group filters.

> **Data caveat — Top Destinations:** Inbound tonnes counted only from downloaded origins.
""")

    b3_col1, b3_col2 = st.columns(2)

    with b3_col1:
        _top_orig = (
            df.groupby(["orig_lga", "orig_name", "orig_state"])["tonnes"]
            .sum().reset_index().nlargest(10, "tonnes")
        )
        fig_b3a = go.Figure(go.Bar(
            x=_top_orig["tonnes"].tolist(),
            y=[f"{n} ({s})" for n, s in zip(_top_orig["orig_name"], _top_orig["orig_state"])],
            orientation="h",
            marker_color=[STATE_COLORS.get(s, "#4B5563") for s in _top_orig["orig_state"]],
            hovertemplate="<b>%{y}</b><br>Outbound Tonnes: %{x:,.0f}<extra></extra>",
        ))
        fig_b3a.update_layout(
            **_PLOTLY_LAYOUT, title_text="Top 10 Origins (outbound tonnes)", title_font_size=13,
            xaxis_title="Tonnes", yaxis_autorange="reversed",
            height=380, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
        )
        st.plotly_chart(fig_b3a, use_container_width=True)

    with b3_col2:
        _top_dest = (
            df.groupby(["dest_lga", "dest_name", "dest_state"])["tonnes"]
            .sum().reset_index().nlargest(10, "tonnes")
        )
        fig_b3b = go.Figure(go.Bar(
            x=_top_dest["tonnes"].tolist(),
            y=[f"{n} ({s})" for n, s in zip(_top_dest["dest_name"], _top_dest["dest_state"])],
            orientation="h",
            marker_color=[STATE_COLORS.get(s, "#4B5563") for s in _top_dest["dest_state"]],
            hovertemplate="<b>%{y}</b><br>Inbound Tonnes: %{x:,.0f}<extra></extra>",
        ))
        fig_b3b.update_layout(
            **_PLOTLY_LAYOUT, title_text="Top 10 Destinations (inbound tonnes)", title_font_size=13,
            xaxis_title="Tonnes", yaxis_autorange="reversed",
            height=380, margin=dict(l=10, r=10, t=40, b=10), showlegend=False,
        )
        st.plotly_chart(fig_b3b, use_container_width=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── B4 + B5 ───────────────────────────────────────────────────────────
    b45_col1, b45_col2 = st.columns(2)

    with b45_col1:
        chart_header("Intra-state vs Inter-state Freight", """
**Intra-state vs Inter-state Freight Split**

Proportion of total tonnes staying within the same state vs crossing state borders.
Responds to the active commodity filter.
""")

        df["is_intra"] = df["orig_state"] == df["dest_state"]
        _intra_t = df[df["is_intra"]]["tonnes"].sum()
        _inter_t = df[~df["is_intra"]]["tonnes"].sum()
        _total_t = _intra_t + _inter_t

        fig_b4 = go.Figure(go.Pie(
            labels=["Intra-state", "Inter-state"],
            values=[_intra_t, _inter_t],
            hole=0.45,
            marker_colors=[_BLUE, _ORANGE],
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} t (%{percent})<extra></extra>",
            textinfo="label+percent", textfont_size=12,
        ))
        fig_b4.update_layout(
            **_PLOTLY_LAYOUT, showlegend=False, height=280,
            margin=dict(l=10, r=10, t=20, b=10),
            annotations=[dict(text=f"{_total_t:,.0f} t", x=0.5, y=0.5,
                              font_size=12, font_color="#374151", showarrow=False)],
        )
        st.plotly_chart(fig_b4, use_container_width=True)

        _states_list = sorted(df["orig_state"].unique())
        _state_split = df.groupby(["orig_state", "is_intra"])["tonnes"].sum().reset_index()
        _intra_vals = [
            float(_state_split[(_state_split["orig_state"] == s) & (_state_split["is_intra"])]["tonnes"].sum())
            for s in _states_list
        ]
        _inter_vals = [
            float(_state_split[(_state_split["orig_state"] == s) & (~_state_split["is_intra"])]["tonnes"].sum())
            for s in _states_list
        ]
        fig_b4b = go.Figure()
        fig_b4b.add_trace(go.Bar(name="Intra-state", x=_states_list, y=_intra_vals,
                                  marker_color=_BLUE,
                                  hovertemplate="<b>%{x}</b><br>Intra: %{y:,.0f} t<extra></extra>"))
        fig_b4b.add_trace(go.Bar(name="Inter-state", x=_states_list, y=_inter_vals,
                                  marker_color=_ORANGE,
                                  hovertemplate="<b>%{x}</b><br>Inter: %{y:,.0f} t<extra></extra>"))
        fig_b4b.update_layout(
            **_PLOTLY_LAYOUT, barmode="stack",
            xaxis_title="Origin State", yaxis_title="Tonnes",
            height=260, margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=-0.3),
        )
        st.plotly_chart(fig_b4b, use_container_width=True)

    with b45_col2:
        chart_header("Cost per Tonne Distribution by State", """
**Cost per Tonne Distribution by Origin State**

Statistical distribution of cost/tonne (AUD) across all corridors per state.

- **Box** = interquartile range (25th–75th percentile)
- **Centre line** = median
- **Dots** = outlier corridors

Zero-cost corridors (no data for selected commodity) excluded.
""")

        fig_b5 = go.Figure()
        for _state in sorted(df["orig_state"].unique()):
            _sdf = df[df["orig_state"] == _state]
            _sdf_nz = _sdf[_sdf["cost_per_tonne"] > 0]
            if len(_sdf_nz) > 1:
                fig_b5.add_trace(go.Box(
                    y=_sdf_nz["cost_per_tonne"], name=_state,
                    marker_color=STATE_COLORS.get(_state, "#4B5563"),
                    boxpoints="outliers",
                    hovertemplate=f"<b>{_state}</b><br>Cost/t: $%{{y:,.2f}}<extra></extra>",
                ))
        fig_b5.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Origin State", yaxis_title="Cost per Tonne (AUD/t)",
            showlegend=False, height=560, margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_b5, use_container_width=True)
        if commodity_filter or industry_filter:
            st.caption("Zero-cost/tonne corridors (no data for selected commodity) excluded from box plot.")

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    st.divider()

# ---------------------------------------------------------------------------
# R1 — Top 15 Destinations (single origin only)
# ---------------------------------------------------------------------------

if not is_national:
    chart_header("Top 15 Destinations", """
**Top 15 Destinations**

The 15 highest-ranked destinations from this origin, sorted by the selected **Rank By** metric.

- **Rank 1 = highest value.** For **Cost/Tonne** this means the most expensive corridor.
- The **selected destination** from Page 1 is highlighted in orange
- Corridors with no data for the selected commodity show zero and appear at the bottom
""")

    _topN_so = df.head(15)
    _topN_so_colors = bar_colors(_topN_so["dest_lga"].tolist())
    _y_labels_so = [f"#{r} {dn}" for r, dn in zip(_topN_so["Rank"], _topN_so["dest_name"])]

    fig_r1 = go.Figure(go.Bar(
        x=_topN_so[rank_field].tolist(),
        y=_y_labels_so,
        orientation="h",
        marker_color=_topN_so_colors,
        hovertemplate=(
            "<b>%{y}</b><br>"
            f"{axis_label}: %{{x:{fmt_str}}}<br>"
            "Tonnes: %{customdata[0]:,.0f}<br>"
            "Cost/t: $%{customdata[1]:,.2f}<br>"
            "CO\u2082: %{customdata[2]:,.1f} t<extra></extra>"
        ),
        customdata=_topN_so[["tonnes", "cost_per_tonne", "co2"]].values.tolist(),
    ))
    fig_r1.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title=axis_label, yaxis_autorange="reversed",
        height=420, margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_r1, use_container_width=True)
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# B7 + R3 side-by-side
# ---------------------------------------------------------------------------

col_b7, col_r3 = st.columns(2)

with col_b7:
    chart_header("Freight Value vs Tonnes", """
**Freight Value vs Tonnes**

Each dot = one OD corridor. Values reflect only the selected commodity type(s).

| Quadrant | Meaning |
|---|---|
| High tonnes + High value | Strategic bulk corridors |
| High tonnes + Low value | Bulk commodities (grain, minerals) |
| Low tonnes + High value | Specialised or premium freight |

Dashed lines = median. Dot size \u221d tonnes.
""", section=False)

    if df["freight_value"].sum() == 0:
        st.info("Freight value not available for the selected commodity type(s).")
    else:
        _med_t_b7 = df["tonnes"].median()
        _med_v_b7 = df["freight_value"].median()
        _max_t_b7 = df["tonnes"].max() or 1

        if is_national:
            fig_b7 = go.Figure()
            fig_b7.add_hline(y=_med_v_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            fig_b7.add_vline(x=_med_t_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            for _state in sorted(df["orig_state"].unique()):
                _sdf = df[df["orig_state"] == _state]
                _sz = (_sdf["tonnes"] / _max_t_b7 * 28 + 4).tolist()
                fig_b7.add_trace(go.Scatter(
                    x=_sdf["tonnes"], y=_sdf["freight_value"],
                    mode="markers", name=_state,
                    marker=dict(color=STATE_COLORS.get(_state, "#4B5563"), size=_sz,
                                line=dict(width=0), opacity=0.75),
                    hovertemplate=(
                        "<b>%{customdata[0]} \u2192 %{customdata[1]}</b><br>"
                        "Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>"
                    ),
                    customdata=_sdf[["orig_name", "dest_name"]].values.tolist(),
                ))
            _show_legend_b7, _legend_b7 = True, dict(orientation="h", y=-0.25)
        else:
            _df_others_b7 = df[df["dest_lga"] != selected_dest_code]
            _df_sel_b7    = df[df["dest_lga"] == selected_dest_code]
            _sz_oth = (_df_others_b7["tonnes"] / _max_t_b7 * 28 + 4).tolist()
            _sz_sel = (_df_sel_b7["tonnes"] / _max_t_b7 * 28 + 4).tolist() if not _df_sel_b7.empty else []

            fig_b7 = go.Figure()
            fig_b7.add_hline(y=_med_v_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            fig_b7.add_vline(x=_med_t_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            fig_b7.add_trace(go.Scatter(
                x=_df_others_b7["tonnes"], y=_df_others_b7["freight_value"],
                mode="markers", name="Other destinations",
                marker=dict(color=_GREY, size=_sz_oth, line=dict(width=0)),
                hovertemplate="<b>%{customdata[0]}</b><br>Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>",
                customdata=_df_others_b7[["dest_name"]].values.tolist(),
            ))
            if not _df_sel_b7.empty:
                fig_b7.add_trace(go.Scatter(
                    x=_df_sel_b7["tonnes"], y=_df_sel_b7["freight_value"],
                    mode="markers+text", name=selected_dest_name or "Selected",
                    marker=dict(color=_ORANGE, size=_sz_sel, line=dict(color="white", width=2)),
                    text=[f"  {selected_dest_name or selected_dest_code}"],
                    textposition="middle right", textfont=dict(size=11, color=_ORANGE),
                    hovertemplate="<b>%{customdata[0]}</b><br>Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>",
                    customdata=_df_sel_b7[["dest_name"]].values.tolist(),
                ))
            _show_legend_b7, _legend_b7 = False, {}

        fig_b7.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Annual Tonnes", yaxis_title="Total Freight Value (AUD)",
            showlegend=_show_legend_b7, legend=_legend_b7,
            height=380, margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_b7, use_container_width=True)
        st.caption("Dashed lines = median tonnes & median freight value. Dot size \u221d tonnes.")

with col_r3:
    chart_header("CO\u2082 vs Transport Cost", """
**CO\u2082 vs Transport Cost**

Environmental vs economic cost trade-off. Values reflect selected commodity type(s).

- **Top-right** — high cost + high emissions (long-haul, high-volume)
- **Bottom-left** — short or minor corridors
- Corridors with no data appear at (0, 0)

Dot size \u221d tonnes.
""", section=False)

    if df["transport_cost"].sum() == 0:
        st.info("Transport cost not available for the selected commodity type(s).")
    else:
        _max_t3 = df["tonnes"].max() or 1
        if is_national:
            _sz3 = (df["tonnes"] / _max_t3 * 28 + 4).tolist()
            fig_r3 = go.Figure()
            fig_r3.add_trace(go.Scatter(
                x=df["transport_cost"], y=df["co2"],
                mode="markers", name="OD corridors",
                marker=dict(color=_GREY, size=_sz3, line=dict(width=0)),
                hovertemplate=(
                    "<b>%{customdata[0]} \u2192 %{customdata[1]}</b><br>"
                    "Transport Cost: $%{x:,.0f}<br>CO\u2082: %{y:,.1f} t<br>"
                    "Tonnes: %{customdata[2]:,.0f}<extra></extra>"
                ),
                customdata=df[["orig_name", "dest_name", "tonnes"]].values.tolist(),
            ))
        else:
            _df_oth3 = df[df["dest_lga"] != selected_dest_code]
            _df_sel3 = df[df["dest_lga"] == selected_dest_code]
            _sz_oth3 = (_df_oth3["tonnes"] / _max_t3 * 28 + 4).tolist()
            _sz_sel3 = (_df_sel3["tonnes"] / _max_t3 * 28 + 4).tolist() if not _df_sel3.empty else []

            fig_r3 = go.Figure()
            fig_r3.add_trace(go.Scatter(
                x=_df_oth3["transport_cost"], y=_df_oth3["co2"],
                mode="markers", name="Other destinations",
                marker=dict(color=_GREY, size=_sz_oth3, line=dict(width=0)),
                hovertemplate="<b>%{customdata[0]}</b><br>Transport Cost: $%{x:,.0f}<br>CO\u2082: %{y:,.1f} t<br>Tonnes: %{customdata[1]:,.0f}<extra></extra>",
                customdata=_df_oth3[["dest_name", "tonnes"]].values.tolist(),
            ))
            if not _df_sel3.empty:
                fig_r3.add_trace(go.Scatter(
                    x=_df_sel3["transport_cost"], y=_df_sel3["co2"],
                    mode="markers+text", name=selected_dest_name or "Selected",
                    marker=dict(color=_ORANGE, size=_sz_sel3, line=dict(color="white", width=2)),
                    text=[f"  {selected_dest_name or selected_dest_code}"],
                    textposition="middle right", textfont=dict(size=11, color=_ORANGE),
                    hovertemplate="<b>%{customdata[0]}</b><br>Transport Cost: $%{x:,.0f}<br>CO\u2082: %{y:,.1f} t<br>Tonnes: %{customdata[1]:,.0f}<extra></extra>",
                    customdata=_df_sel3[["dest_name", "tonnes"]].values.tolist(),
                ))

        fig_r3.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Total Transport Cost (AUD)", yaxis_title="CO\u2082 Emissions (t)",
            showlegend=False, height=380, margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_r3, use_container_width=True)
        st.caption("Cost vs emissions trade-off. Dot size \u221d tonnes.")

st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# R4 — Full Rankings Table
# ---------------------------------------------------------------------------

_filter_parts_csv = []
if industry_filter:
    _filter_parts_csv.append("ind_" + "_".join(sorted(industry_filter)))
if commodity_filter:
    _filter_parts_csv.append("comm_" + "_".join(sorted(commodity_filter)))
_filter_suffix = ("_" + "_".join(_filter_parts_csv)) if _filter_parts_csv else ""

_ind_note = ""
if filter_mode == "industry_group" and industry_filter:
    _ind_note += f" | Industry groups: {', '.join(sorted(i.replace('_',' ').title() for i in industry_filter))}"
elif filter_mode == "sector" and commodity_filter:
    _ind_note += f" | Sectors: {', '.join(_fmt_sector(s) for s in selected_sectors)} → {', '.join(_fmt_commodity(c) for c in sorted(commodity_filter))}"
elif filter_mode == "industry_dict" and commodity_filter:
    _ind_note += f" | Industries: {', '.join(i.replace('_',' ').title() for i in selected_industries)} → {', '.join(_fmt_commodity(c) for c in sorted(commodity_filter))}"

chart_header("Full Rankings Table", f"""
**Full Rankings Table**

All OD corridors sorted by the selected **Rank By** metric.{_ind_note}

> **Rank 1 = highest value.** For **Cost/Tonne**, Rank 1 is the most expensive corridor. To find the cheapest, sort ascending by clicking the column header.

**Columns:**
- **Tonnes** — annual tonnes for selected commodity type(s)
- **Cost/Tonne** — transport cost ÷ tonnes (AUD/t)
- **Transport Cost** — total annual transport cost (AUD)
- **Freight Value** — total value of goods (AUD)
- **CO\u2082** — total CO\u2082-equivalent emissions (t)
- **Avg Distance** — weighted average trip distance (km)

> Corridors with no matching commodity show zero and appear at the bottom.
""")

if is_national:
    st.markdown(
        f'<div class="helper-text">All <strong>{total_count:,}</strong> OD corridors, '
        f'sorted by <strong>{rank_metric}</strong>.</div>',
        unsafe_allow_html=True,
    )
    df_table = df[[
        "Rank", "orig_name", "orig_state", "dest_name", "dest_state",
        "tonnes", "cost_per_tonne", "transport_cost",
        "freight_value", "co2", "avg_distance", "trips",
    ]].rename(columns={
        "orig_name": "Origin", "orig_state": "Orig State",
        "dest_name": "Destination", "dest_state": "Dest State",
        "tonnes": "Tonnes", "cost_per_tonne": "Cost/Tonne ($)",
        "transport_cost": "Transport Cost ($)", "freight_value": "Freight Value ($)",
        "co2": "CO\u2082 (t)", "avg_distance": "Avg Distance (km)", "trips": "Trips",
    })
    col_config = {
        "Rank":               st.column_config.NumberColumn(format="%d",   width="small"),
        "Origin":             st.column_config.TextColumn(width="medium"),
        "Orig State":         st.column_config.TextColumn(width="small"),
        "Destination":        st.column_config.TextColumn(width="medium"),
        "Dest State":         st.column_config.TextColumn(width="small"),
        "Tonnes":             st.column_config.NumberColumn(format="%.0f"),
        "Cost/Tonne ($)":    st.column_config.NumberColumn(format="$%.2f"),
        "Transport Cost ($)": st.column_config.NumberColumn(format="$%.0f"),
        "Freight Value ($)":  st.column_config.NumberColumn(format="$%.0f"),
        "CO\u2082 (t)":       st.column_config.NumberColumn(format="%.1f"),
        "Avg Distance (km)":  st.column_config.NumberColumn(format="%.1f"),
        "Trips":              st.column_config.NumberColumn(format="%d",   width="small"),
    }
    csv_name = f"l3_rankings_national_by_{rank_field}{_filter_suffix}.csv"
else:
    st.markdown(
        f'<div class="helper-text">'
        f'All {total_count} destinations from <strong>{orig_name}</strong>, '
        f'sorted by <strong>{rank_metric}</strong>. '
        + (f'Selected destination <strong>{selected_dest_name}</strong> is rank '
           f'<strong>#{selected_rank}</strong>.' if selected_rank else "")
        + '</div>',
        unsafe_allow_html=True,
    )
    df_table = df[[
        "Rank", "dest_name", "dest_state",
        "tonnes", "cost_per_tonne", "transport_cost",
        "freight_value", "co2", "avg_distance", "trips",
    ]].rename(columns={
        "dest_name": "Destination", "dest_state": "State",
        "tonnes": "Tonnes", "cost_per_tonne": "Cost/Tonne ($)",
        "transport_cost": "Transport Cost ($)", "freight_value": "Freight Value ($)",
        "co2": "CO\u2082 (t)", "avg_distance": "Avg Distance (km)", "trips": "Trips",
    })
    col_config = {
        "Rank":               st.column_config.NumberColumn(format="%d",   width="small"),
        "Destination":        st.column_config.TextColumn(width="medium"),
        "State":              st.column_config.TextColumn(width="small"),
        "Tonnes":             st.column_config.NumberColumn(format="%.0f"),
        "Cost/Tonne ($)":    st.column_config.NumberColumn(format="$%.2f"),
        "Transport Cost ($)": st.column_config.NumberColumn(format="$%.0f"),
        "Freight Value ($)":  st.column_config.NumberColumn(format="$%.0f"),
        "CO\u2082 (t)":       st.column_config.NumberColumn(format="%.1f"),
        "Avg Distance (km)":  st.column_config.NumberColumn(format="%.1f"),
        "Trips":              st.column_config.NumberColumn(format="%d",   width="small"),
    }
    csv_name = f"l3_rankings_{orig_code}_by_{rank_field}{_filter_suffix}.csv"

st.dataframe(
    df_table, use_container_width=True, hide_index=True,
    height=420, column_config=col_config,
)
st.download_button(
    label="\u2b07 Download Rankings CSV",
    data=df_table.to_csv(index=False).encode("utf-8"),
    file_name=csv_name,
    mime="text/csv",
)

st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

# Bottom back links
col_back1b, _ = st.columns([1, 6])
with col_back1b:
    st.page_link("CSIRO_TraNSIT_Dashboard.py", label="\u2190 OD Metrics", icon="\U0001f69b")
