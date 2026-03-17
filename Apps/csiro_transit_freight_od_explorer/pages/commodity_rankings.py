"""
pages/commodity_rankings.py  —  Commodity Corridor Rankings (Page 3)

Identical to od_rankings.py with an additional commodity/freight type filter.
Rankings reflect only the selected freight types from local commodityreport data.

The commodity filter is NOT available in Online (densitymap) API mode —
densitymap returns only aggregated totals with no per-industry breakdown.

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
from api import _compute_totals, fetch_origin_destinations
from downloader import start_download, cancel_download, get_progress

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Commodity Rankings \u2014 FreightOD",
    page_icon="\U0001f3f7\ufe0f",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS  (identical to od_rankings.py)
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
# Industry helpers
# ---------------------------------------------------------------------------

# Path to local data (one level up from pages/)
LOCAL_DATA_ROOT = pathlib.Path(__file__).parent.parent / "api_local_data" / "level2"

# Complete list of all known TraNSIT industry identifiers (from full data scan)
_HARDCODED_INDUSTRIES: list[str] = [
    "alcohol_beverage", "beverage", "chemicals", "dairy_product", "fibre",
    "food", "fruit", "fuel", "grains", "household_general", "livestock",
    "meat", "medicines", "minerals", "nuts", "other_retail_ess", "ppe",
    "seafood", "sugar", "tissue_product", "vegetables", "vehicles",
    "viticulture", "waste", "wood_product",
]

_DISPLAY_OVERRIDES: dict[str, str] = {
    "ppe":              "PPE",
    "other_retail_ess": "Other Retail (Essential)",
    "alcohol_beverage": "Alcohol & Beverage",
}


def _fmt(s: str) -> str:
    """Convert snake_case industry id to human-readable display name."""
    return _DISPLAY_OVERRIDES.get(s, s.replace("_", " ").title())


def _zero_totals() -> dict:
    """Return all-zero headline metrics for an OD pair with no matching commodity records."""
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
def _get_industries_from_local_data() -> list[str]:
    """
    Scan up to 5 local JSON files per state directory and return all unique
    industry identifiers found.  Per-state sampling ensures industries from
    every state are discovered (not just ACT/NSW).
    Cached for the session lifetime. Returns [] if no local data exists.
    """
    if not LOCAL_DATA_ROOT.exists():
        return []
    found: set[str] = set()
    for state_dir in sorted(LOCAL_DATA_ROOT.iterdir()):
        if not state_dir.is_dir():
            continue
        for json_file in list(sorted(state_dir.glob("*.json")))[:5]:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                for records in data.get("destinations", {}).values():
                    for r in records:
                        if r.get("industry"):
                            found.add(r["industry"])
            except (OSError, json.JSONDecodeError):
                continue
    return sorted(found)


# ---------------------------------------------------------------------------
# Filtered data loading functions
# ---------------------------------------------------------------------------

def _load_all_od_pairs_filtered(
    industry_filter: frozenset | None,
) -> tuple[list[dict], str | None]:
    """
    Load all OD pairs from local data, applying industry filter before aggregation.

    Destinations that originally had freight but have none matching the selected
    industry are still included with zero metrics (they sort to the bottom).
    Destinations with no freight at all (empty records) are excluded.
    """
    if not LOCAL_DATA_ROOT.exists():
        return [], f"Local data directory not found: {LOCAL_DATA_ROOT}"

    rows: list[dict] = []
    for state_dir in sorted(LOCAL_DATA_ROOT.iterdir()):
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
                    continue  # skip destinations with no freight at all
                if industry_filter:
                    filtered = [r for r in records if r.get("industry") in industry_filter]
                else:
                    filtered = records
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
        return [], "No local data found."
    return rows, None


def _load_local_origin_data_filtered(
    orig_lga: str,
    orig_state: str,
    industry_filter: frozenset | None,
) -> tuple[dict | None, str | None]:
    """
    Load local data for one origin, applying industry filter before aggregation.
    Destinations that had freight but none matching the filter get zero metrics.
    """
    path = LOCAL_DATA_ROOT / orig_state / f"{orig_lga}.json"
    if not path.exists():
        return None, f"Local data not found at: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Failed to read local file: {exc}"

    result: dict[str, dict] = {}
    for dest_lga, records in data.get("destinations", {}).items():
        if not records:
            continue
        if industry_filter:
            filtered = [r for r in records if r.get("industry") in industry_filter]
        else:
            filtered = records
        result[dest_lga] = (
            _compute_totals(filtered, is_local=(orig_lga == dest_lga))
            if filtered
            else _zero_totals()
        )
    return result, None


@st.cache_data(show_spinner=False)
def _cached_od_pairs_filtered(industry_filter_frozen: frozenset | None):
    return _load_all_od_pairs_filtered(industry_filter_frozen)


@st.cache_data(show_spinner=False)
def _cached_local_origin_filtered(
    orig_lga: str, orig_state: str, industry_filter_frozen: frozenset | None
):
    return _load_local_origin_data_filtered(orig_lga, orig_state, industry_filter_frozen)


@st.cache_data(show_spinner=False)
def _cached_origin_dests(orig_lga: str):
    return fetch_origin_destinations(orig_lga)


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
            🏷️ Commodity Rankings
        </div>
        <div style="font-size:13px; font-weight:600; color:#A8D4F5; margin-top:2px;">
            Top Corridors by Freight Type
        </div>
        <div style="font-size:12px; color:#7BA7CC; margin-top:6px; line-height:1.5;">
            Filter rankings by commodity type<br>
            CSIRO TraNSIT &middot; SIM-AU-BASELINE
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

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
            key="ind_orig_state",
            label_visibility="collapsed",
        )
        orig_lga_opts = SORTED_NAMES if orig_state == "All states" else STATE_LGAS[orig_state]

        if "ind_orig_lga_name" not in st.session_state:
            st.session_state["ind_orig_lga_name"] = orig_lga_opts[0]
        if st.session_state["ind_orig_lga_name"] not in orig_lga_opts:
            st.session_state["ind_orig_lga_name"] = orig_lga_opts[0]

        orig_name = st.selectbox(
            "Origin LGA",
            options=orig_lga_opts,
            index=orig_lga_opts.index(st.session_state["ind_orig_lga_name"]),
            label_visibility="collapsed",
        )
        st.session_state["ind_orig_lga_name"] = orig_name
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

    # ── INDUSTRY LIST SOURCE ──────────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Industry List Source</div>',
        unsafe_allow_html=True,
    )
    industry_source = st.radio(
        "Industry list source",
        options=["\U0001f50d Auto-detect from local data", "\U0001f4cb Use predefined list"],
        index=0,
        label_visibility="collapsed",
        key="ind_source",
    )

    if industry_source.startswith("\U0001f50d"):
        _detected = _get_industries_from_local_data()
        industry_opts = _detected if _detected else _HARDCODED_INDUSTRIES
        if not _detected:
            st.markdown(
                '<div style="font-size:10px; color:#F59E0B; margin-top:2px;">'
                '\u26a0 No local data found \u2014 using predefined list.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="font-size:10px; color:#86EFAC; margin-top:2px;">'
                f'\u2713 {len(industry_opts)} types detected from local data.</div>',
                unsafe_allow_html=True,
            )
    else:
        industry_opts = _HARDCODED_INDUSTRIES
        st.markdown(
            f'<div style="font-size:10px; color:#93C5FD; margin-top:2px;">'
            f'\U0001f4cb {len(industry_opts)} predefined industry types.</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── FILTER BY COMMODITY TYPE ──────────────────────────────────────────
    st.markdown(
        '<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        'letter-spacing:0.8px; color:#7BA7CC; margin-bottom:8px;">Filter by Commodity Type</div>',
        unsafe_allow_html=True,
    )

    _display_opts = sorted([_fmt(i) for i in industry_opts])
    selected_industries_display = st.multiselect(
        "Commodity types",
        options=_display_opts,
        default=[],
        placeholder="All types (no filter)",
        label_visibility="collapsed",
        disabled=is_online,
        key="ind_filter",
    )

    if is_online:
        st.markdown(
            '<div style="font-size:10px; color:#F59E0B; margin-top:4px; line-height:1.5;">'
            '\u26a0 Commodity filter requires <strong>Local Data</strong> mode. '
            'Switch Data Source to enable this filter.</div>',
            unsafe_allow_html=True,
        )

    # Map display names back to internal keys
    _display_to_key: dict[str, str] = {_fmt(i): i for i in industry_opts}
    industry_filter: frozenset | None = (
        frozenset(
            _display_to_key[d]
            for d in selected_industries_display
            if d in _display_to_key
        )
        if selected_industries_display
        else None
    )

    st.divider()

    st.markdown(
        '<div style="color:#5A8AB0; font-size:11px; line-height:1.7;">'
        'Commodity Rankings<br>'
        'Dataset: SIM-AU-BASELINE<br>'
        f'Scope: {"National (all origins)" if is_national else "Single origin"}<br>'
        f'Source: {"Local JSON cache" if is_national else ("\U0001f4f6 densitymap API" if is_online else "Local JSON cache")}<br>'
        f'Commodity: {f"{len(selected_industries_display)} type(s) selected" if selected_industries_display else "All types"}'
        '</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

if is_national:
    st.markdown("""
    <div class="route-header">
        <span class="route-title">Commodity Corridor Rankings</span>
    </div>
    <div class="route-subtitle">
        Top freight corridors across all Australian LGAs &nbsp;&middot;&nbsp;
        SIM-AU-BASELINE &nbsp;&middot;&nbsp; Road &nbsp;&middot;&nbsp; Local Data &nbsp;&middot;&nbsp; by commodity type
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
        <span style="font-size:14px; color:#9CA3AF; font-weight:400;">Commodity View</span>
    </div>
    <div class="route-subtitle">
        OD corridor rankings &nbsp;&middot;&nbsp; SIM-AU-BASELINE &nbsp;&middot;&nbsp; Road
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# Back links
col_back1, col_back2, _ = st.columns([1, 1, 5])
with col_back1:
    st.page_link("app.py", label="\u2190 OD Metrics", icon="\U0001f69b")
with col_back2:
    st.page_link("pages/od_rankings.py", label="\u2190 All Types", icon="\U0001f4ca")

st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Download expander
# ---------------------------------------------------------------------------

with st.expander("\U0001f4e5 Update / Download Local Data", expanded=False):
    _prog = get_progress()

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
        if st.button("\u23f9 Cancel download"):
            cancel_download()
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
        if st.button("Clear status"):
            _prog.reset()
            st.rerun()

    else:
        _dl_state_opts = ["All States"] + sorted(STATE_LGAS.keys())
        _dl_state = st.selectbox(
            "Download scope",
            options=_dl_state_opts,
            help="Select a single state for a faster partial download.",
        )
        _force = st.checkbox("Force re-download (overwrite already-cached files)", value=False)
        _state_filter = None if _dl_state == "All States" else _dl_state
        _n_lgas = (
            len(LGA_CODES) if _state_filter is None
            else len(STATE_LGAS.get(_state_filter, []))
        )
        _est_min = max(1, int(_n_lgas * 1.5))
        st.caption(
            f"**{_n_lgas} LGAs** \u2014 estimated time: ~{_est_min} min "
            f"({'all states' if _state_filter is None else _state_filter}). "
            "Existing files are skipped unless Force is checked."
        )
        if st.button("\u25b6 Start Download", type="primary"):
            start_download(state_filter=_state_filter, force=_force)
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
    with st.spinner("Loading OD pairs from local data\u2026"):
        all_rows, data_error = _cached_od_pairs_filtered(industry_filter)

    if data_error or not all_rows:
        st.warning(
            "**No local data found.**\n\n"
            "Use the **\U0001f4e5 Update / Download Local Data** panel above to download data.\n\n"
            "Select a state (e.g. VIC for a quick test) and click **\u25b6 Start Download**.",
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
    data_note = (
        f"Loaded **{len(rows):,}** OD corridors from **{total_origins}** origins "
        f"({'selected states' if state_filter else 'all states'}) \u2014 "
        "local commodityreport cache."
    )

# ── Single Origin scope ─────────────────────────────────────────────────────
else:
    selected_dest_code = st.session_state.get("shared_dest_code", "")
    selected_dest_name = st.session_state.get("shared_dest_name", "")

    if is_online:
        # Online mode: no industry filter available
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
            "Numbers from the **densitymap** endpoint \u2014 "
            "these differ from commodityreport values on Page 1. "
            "Use for ranking/comparison only."
        )

    else:
        # Local Data mode: apply industry filter
        local_dict, local_error = _cached_local_origin_filtered(
            orig_code, orig_state_abbr, industry_filter
        )
        if local_dict is None:
            st.warning(
                f"**No local data found for {orig_name} ({orig_code}).**\n\n"
                "Use the **\U0001f4e5 Update / Download Local Data** panel above, "
                "or switch to **\U0001f4f6 Online (API)**.",
                icon="\u26a0\ufe0f",
            )
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
        data_note = (
            "Numbers from the **local commodityreport cache** \u2014 "
            "consistent with the headline metrics shown on Page 1."
        )

if not rows:
    st.info("No destination data available.", icon="\u2139\ufe0f")
    st.stop()

st.info(data_note, icon="\u2139\ufe0f")

# ── Commodity filter active indicator ─────────────────────────────────────
if industry_filter and not is_online:
    _fmt_names = sorted(_fmt(i) for i in industry_filter)
    st.info(
        f"\U0001f4e6 **Commodity filter active:** showing only "
        f"**{', '.join(_fmt_names)}**. "
        "Metrics reflect selected types only \u2014 not total corridor freight. "
        "Corridors with no data for the selected type(s) show zero and appear at the bottom.",
        icon="\U0001f50d",
    )

# ---------------------------------------------------------------------------
# Sort + rank
# ---------------------------------------------------------------------------

df = pd.DataFrame(rows)
df = df.sort_values(rank_field, ascending=False).reset_index(drop=True)
df.insert(0, "Rank", range(1, len(df) + 1))

total_count = len(df)

# For single origin: find rank of selected destination (from Page 1 session state)
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

Aggregated totals across all OD corridors loaded from the local data cache.

All values update when you apply a **Filter by Origin State** or **Commodity Type** filter.

> **Median Cost/Tonne** is the unweighted median across all corridors (each corridor counted equally regardless of freight volume). This may differ from a volume-weighted average.

> **Tip:** Use the Download panel above to add more states for a more complete national picture.
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

Each cell shows total annual tonnes moving from an **origin state** (rows) to a **destination state** (columns).

- **Diagonal cells** = intra-state freight
- **Off-diagonal cells** = inter-state freight
- **Darker colour** = higher freight volume

When a commodity filter is active, only tonnes for the selected commodity types are shown.

*Only states with downloaded data are shown.*
""")

    _state_flow = df.groupby(["orig_state", "dest_state"])["tonnes"].sum().reset_index()
    _states_hm = sorted(
        set(_state_flow["orig_state"].tolist() + _state_flow["dest_state"].tolist())
    )
    _matrix = pd.DataFrame(0.0, index=_states_hm, columns=_states_hm)
    for _, _r in _state_flow.iterrows():
        if _r["orig_state"] in _matrix.index and _r["dest_state"] in _matrix.columns:
            _matrix.loc[_r["orig_state"], _r["dest_state"]] = _r["tonnes"]

    _text_matrix = [
        [f"{v:,.0f} t" if v > 0 else "" for v in row]
        for row in _matrix.values
    ]

    fig_hm = go.Figure(go.Heatmap(
        z=_matrix.values,
        x=_states_hm,
        y=_states_hm,
        text=_text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=11),
        colorscale="Blues",
        hoverongaps=False,
        hovertemplate="<b>%{y} \u2192 %{x}</b><br>Tonnes: %{z:,.0f}<extra></extra>",
        colorbar=dict(title="Tonnes", tickformat=",.0f"),
    ))
    fig_hm.update_layout(
        **_PLOTLY_LAYOUT,
        xaxis_title="Destination State",
        yaxis_title="Origin State",
        height=max(320, len(_states_hm) * 55),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("Diagonal = intra-state freight. Off-diagonal = inter-state freight.")

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── R1 (B6) — Top 20 National OD Corridors ───────────────────────────
    chart_header("Top 20 National OD Corridors", """
**Top 20 National OD Corridors**

The 20 highest-ranked freight corridors, sorted by the selected **Rank By** metric.

- **Rank 1 = highest value.** For **Cost/Tonne** this means the most expensive corridor.
- Bars are coloured by **origin state**
- When a commodity filter is active, values reflect only the selected types

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
        xaxis_title=axis_label,
        yaxis_autorange="reversed",
        height=500,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(_fig_r1_nat, use_container_width=True)

    _states_in_top_nat = sorted(_topN_nat["orig_state"].unique())
    _legend_html_nat = " ".join([
        f'<span style="background:{STATE_COLORS.get(s, "#4B5563")}; color:white; '
        f'padding:2px 8px; border-radius:3px; font-size:11px; font-weight:600; '
        f'margin-right:4px;">{s}</span>'
        for s in _states_in_top_nat
    ])
    st.markdown(
        f'<div style="margin-top:4px; margin-bottom:8px;">{_legend_html_nat}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── B3 — Top Origins / Top Destinations ──────────────────────────────
    chart_header("Top Origins & Top Destinations", """
**Top Origins & Top Destinations**

**Left chart** — Top 10 origin LGAs ranked by total outbound tonnes to all destinations.

**Right chart** — Top 10 destination LGAs ranked by total inbound tonnes received from all origins.

When a commodity filter is active, both charts reflect only the selected commodity types.

> **Data caveat — Top Destinations:** Inbound tonnes are only counted from origins that have been downloaded. Destinations receiving large freight volumes from states not yet downloaded may be under-ranked.
""")

    b3_col1, b3_col2 = st.columns(2)

    with b3_col1:
        _top_orig = (
            df.groupby(["orig_lga", "orig_name", "orig_state"])["tonnes"]
            .sum().reset_index().nlargest(10, "tonnes")
        )
        _top_orig_labels = [
            f"{n} ({s})" for n, s in zip(_top_orig["orig_name"], _top_orig["orig_state"])
        ]
        _top_orig_colors = [STATE_COLORS.get(s, "#4B5563") for s in _top_orig["orig_state"]]
        fig_b3a = go.Figure(go.Bar(
            x=_top_orig["tonnes"].tolist(),
            y=_top_orig_labels,
            orientation="h",
            marker_color=_top_orig_colors,
            hovertemplate="<b>%{y}</b><br>Outbound Tonnes: %{x:,.0f}<extra></extra>",
        ))
        fig_b3a.update_layout(
            **_PLOTLY_LAYOUT,
            title_text="Top 10 Origins (outbound tonnes)",
            title_font_size=13,
            xaxis_title="Tonnes",
            yaxis_autorange="reversed",
            height=380,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_b3a, use_container_width=True)

    with b3_col2:
        _top_dest = (
            df.groupby(["dest_lga", "dest_name", "dest_state"])["tonnes"]
            .sum().reset_index().nlargest(10, "tonnes")
        )
        _top_dest_labels = [
            f"{n} ({s})" for n, s in zip(_top_dest["dest_name"], _top_dest["dest_state"])
        ]
        _top_dest_colors = [STATE_COLORS.get(s, "#4B5563") for s in _top_dest["dest_state"]]
        fig_b3b = go.Figure(go.Bar(
            x=_top_dest["tonnes"].tolist(),
            y=_top_dest_labels,
            orientation="h",
            marker_color=_top_dest_colors,
            hovertemplate="<b>%{y}</b><br>Inbound Tonnes: %{x:,.0f}<extra></extra>",
        ))
        fig_b3b.update_layout(
            **_PLOTLY_LAYOUT,
            title_text="Top 10 Destinations (inbound tonnes)",
            title_font_size=13,
            xaxis_title="Tonnes",
            yaxis_autorange="reversed",
            height=380,
            margin=dict(l=10, r=10, t=40, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_b3b, use_container_width=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ── B4 + B5 — Intra/Inter Split & Cost Distribution by State ─────────
    b45_col1, b45_col2 = st.columns(2)

    with b45_col1:
        chart_header("Intra-state vs Inter-state Freight", """
**Intra-state vs Inter-state Freight Split**

**Donut** — Proportion of total tonnes staying within the same state vs crossing a state border.

**Bar chart** — The intra/inter breakdown per individual state.

When a commodity filter is active, only tonnes for the selected types are used.
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
            textinfo="label+percent",
            textfont_size=12,
        ))
        fig_b4.update_layout(
            **_PLOTLY_LAYOUT,
            showlegend=False,
            height=280,
            margin=dict(l=10, r=10, t=20, b=10),
            annotations=[dict(
                text=f"{_total_t:,.0f} t",
                x=0.5, y=0.5,
                font_size=12, font_color="#374151", showarrow=False,
            )],
        )
        st.plotly_chart(fig_b4, use_container_width=True)

        _states_list = sorted(df["orig_state"].unique())
        _state_split = df.groupby(["orig_state", "is_intra"])["tonnes"].sum().reset_index()
        _intra_vals = [
            float(_state_split[
                (_state_split["orig_state"] == s) & (_state_split["is_intra"])
            ]["tonnes"].sum())
            for s in _states_list
        ]
        _inter_vals = [
            float(_state_split[
                (_state_split["orig_state"] == s) & (~_state_split["is_intra"])
            ]["tonnes"].sum())
            for s in _states_list
        ]
        fig_b4b = go.Figure()
        fig_b4b.add_trace(go.Bar(
            name="Intra-state", x=_states_list, y=_intra_vals, marker_color=_BLUE,
            hovertemplate="<b>%{x}</b><br>Intra: %{y:,.0f} t<extra></extra>",
        ))
        fig_b4b.add_trace(go.Bar(
            name="Inter-state", x=_states_list, y=_inter_vals, marker_color=_ORANGE,
            hovertemplate="<b>%{x}</b><br>Inter: %{y:,.0f} t<extra></extra>",
        ))
        fig_b4b.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="stack",
            xaxis_title="Origin State",
            yaxis_title="Tonnes",
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=-0.3),
        )
        st.plotly_chart(fig_b4b, use_container_width=True)

    with b45_col2:
        chart_header("Cost per Tonne Distribution by State", """
**Cost per Tonne Distribution by Origin State**

Each box shows the statistical distribution of cost/tonne (AUD) across all freight corridors originating from that state:
- **Box** = interquartile range (25th–75th percentile)
- **Centre line** = median cost/tonne
- **Whiskers** = 1.5× IQR
- **Dots** = statistical outlier corridors

When a commodity filter is active, corridors with zero tonnes for the selected type(s) may skew the distribution.
""")

        fig_b5 = go.Figure()
        for _state in sorted(df["orig_state"].unique()):
            _sdf = df[df["orig_state"] == _state]
            _sdf_nonzero = _sdf[_sdf["cost_per_tonne"] > 0]
            if len(_sdf_nonzero) > 1:
                fig_b5.add_trace(go.Box(
                    y=_sdf_nonzero["cost_per_tonne"],
                    name=_state,
                    marker_color=STATE_COLORS.get(_state, "#4B5563"),
                    boxpoints="outliers",
                    hovertemplate=f"<b>{_state}</b><br>Cost/t: $%{{y:,.2f}}<extra></extra>",
                ))
        fig_b5.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Origin State",
            yaxis_title="Cost per Tonne (AUD/t)",
            showlegend=False,
            height=560,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_b5, use_container_width=True)
        if industry_filter:
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
- Corridors with no data for the selected commodity type(s) show zero and appear at the bottom

Change the metric using the **Rank By** selector in the sidebar.
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
        xaxis_title=axis_label,
        yaxis_autorange="reversed",
        height=420,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_r1, use_container_width=True)
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# B7 + R3 side-by-side
# ---------------------------------------------------------------------------

col_b7, col_r3 = st.columns(2)

# ── B7 — Freight Value vs Tonnes ──────────────────────────────────────────
with col_b7:
    chart_header("Freight Value vs Tonnes", """
**Freight Value vs Tonnes**

Each dot represents one OD corridor. When a commodity filter is active, both axes reflect only the selected types.

**Interpreting quadrants** (relative to median lines):

| Quadrant | Meaning |
|---|---|
| High tonnes + High value | Strategic high-volume bulk corridors |
| High tonnes + Low value | Bulk commodity flows (e.g. grain, minerals) |
| Low tonnes + High value | Specialised or premium freight |
| Low tonnes + Low value | Minor or zero-commodity corridors |

Dashed lines = median tonnes & median freight value. Dot size ∝ tonnes.
""", section=False)

    if df["freight_value"].sum() == 0:
        st.info("Freight value data not available for the selected commodity type(s).")
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
                    marker=dict(
                        color=STATE_COLORS.get(_state, "#4B5563"),
                        size=_sz, line=dict(width=0), opacity=0.75,
                    ),
                    hovertemplate=(
                        "<b>%{customdata[0]} \u2192 %{customdata[1]}</b><br>"
                        "Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>"
                    ),
                    customdata=_sdf[["orig_name", "dest_name"]].values.tolist(),
                ))
            _show_legend_b7 = True
            _legend_b7 = dict(orientation="h", y=-0.25)
        else:
            _df_others_b7 = df[df["dest_lga"] != selected_dest_code]
            _df_sel_b7    = df[df["dest_lga"] == selected_dest_code]
            _sz_others_b7 = (_df_others_b7["tonnes"] / _max_t_b7 * 28 + 4).tolist()
            _sz_sel_b7    = (_df_sel_b7["tonnes"] / _max_t_b7 * 28 + 4).tolist() if not _df_sel_b7.empty else []

            fig_b7 = go.Figure()
            fig_b7.add_hline(y=_med_v_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            fig_b7.add_vline(x=_med_t_b7, line_dash="dot", line_color="#D1D5DB", line_width=1)
            fig_b7.add_trace(go.Scatter(
                x=_df_others_b7["tonnes"], y=_df_others_b7["freight_value"],
                mode="markers", name="Other destinations",
                marker=dict(color=_GREY, size=_sz_others_b7, line=dict(width=0)),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>"
                ),
                customdata=_df_others_b7[["dest_name"]].values.tolist(),
            ))
            if not _df_sel_b7.empty:
                fig_b7.add_trace(go.Scatter(
                    x=_df_sel_b7["tonnes"], y=_df_sel_b7["freight_value"],
                    mode="markers+text", name=selected_dest_name or "Selected",
                    marker=dict(color=_ORANGE, size=_sz_sel_b7, line=dict(color="white", width=2)),
                    text=[f"  {selected_dest_name or selected_dest_code}"],
                    textposition="middle right",
                    textfont=dict(size=11, color=_ORANGE),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Tonnes: %{x:,.0f}<br>Freight Value: $%{y:,.0f}<extra></extra>"
                    ),
                    customdata=_df_sel_b7[["dest_name"]].values.tolist(),
                ))
            _show_legend_b7 = False
            _legend_b7 = {}

        fig_b7.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Annual Tonnes",
            yaxis_title="Total Freight Value (AUD)",
            showlegend=_show_legend_b7,
            legend=_legend_b7,
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_b7, use_container_width=True)
        st.caption("Dashed lines = median tonnes & median freight value. Dot size \u221d tonnes.")

# ── R3 — CO₂ vs Transport Cost ────────────────────────────────────────────
with col_r3:
    chart_header("CO\u2082 vs Transport Cost", """
**CO₂ vs Transport Cost**

Environmental vs economic cost trade-off. When a commodity filter is active, values reflect only the selected types.

- **Top-right** — high cost and high emissions (long-haul, high-volume)
- **Bottom-left** — low cost and low emissions (short or minor corridors)
- Corridors with zero data for the selected commodity appear at the origin (0, 0)

Dot size ∝ tonnes.
""", section=False)

    if df["transport_cost"].sum() == 0:
        st.info("Transport cost data not available for the selected commodity type(s).")
    else:
        if is_national:
            _max_t3 = df["tonnes"].max() or 1
            _sz3 = (df["tonnes"] / _max_t3 * 28 + 4).tolist()
            fig_r3 = go.Figure()
            fig_r3.add_trace(go.Scatter(
                x=df["transport_cost"], y=df["co2"],
                mode="markers", name="OD corridors",
                marker=dict(color=_GREY, size=_sz3, line=dict(width=0)),
                hovertemplate=(
                    "<b>%{customdata[0]} \u2192 %{customdata[1]}</b><br>"
                    "Transport Cost: $%{x:,.0f}<br>"
                    "CO\u2082: %{y:,.1f} t<br>"
                    "Tonnes: %{customdata[2]:,.0f}<extra></extra>"
                ),
                customdata=df[["orig_name", "dest_name", "tonnes"]].values.tolist(),
            ))
        else:
            _df_others3 = df[df["dest_lga"] != selected_dest_code]
            _df_sel3    = df[df["dest_lga"] == selected_dest_code]
            _max_t3 = df["tonnes"].max() or 1
            _sz_others3 = (_df_others3["tonnes"] / _max_t3 * 28 + 4).tolist()
            _sz_sel3    = (_df_sel3["tonnes"] / _max_t3 * 28 + 4).tolist() if not _df_sel3.empty else []

            fig_r3 = go.Figure()
            fig_r3.add_trace(go.Scatter(
                x=_df_others3["transport_cost"], y=_df_others3["co2"],
                mode="markers", name="Other destinations",
                marker=dict(color=_GREY, size=_sz_others3, line=dict(width=0)),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Transport Cost: $%{x:,.0f}<br>"
                    "CO\u2082: %{y:,.1f} t<br>"
                    "Tonnes: %{customdata[1]:,.0f}<extra></extra>"
                ),
                customdata=_df_others3[["dest_name", "tonnes"]].values.tolist(),
            ))
            if not _df_sel3.empty:
                fig_r3.add_trace(go.Scatter(
                    x=_df_sel3["transport_cost"], y=_df_sel3["co2"],
                    mode="markers+text", name=selected_dest_name or "Selected",
                    marker=dict(color=_ORANGE, size=_sz_sel3, line=dict(color="white", width=2)),
                    text=[f"  {selected_dest_name or selected_dest_code}"],
                    textposition="middle right",
                    textfont=dict(size=11, color=_ORANGE),
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Transport Cost: $%{x:,.0f}<br>"
                        "CO\u2082: %{y:,.1f} t<br>"
                        "Tonnes: %{customdata[1]:,.0f}<extra></extra>"
                    ),
                    customdata=_df_sel3[["dest_name", "tonnes"]].values.tolist(),
                ))

        fig_r3.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="Total Transport Cost (AUD)",
            yaxis_title="CO\u2082 Emissions (t)",
            showlegend=False,
            height=380,
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig_r3, use_container_width=True)
        st.caption("Cost vs emissions trade-off across all corridors. Dot size \u221d tonnes.")

st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# R4 — Full Rankings Table
# ---------------------------------------------------------------------------

_filter_note = (
    f" | Commodity filter: {', '.join(sorted(_fmt(i) for i in industry_filter))}"
    if industry_filter else ""
)

chart_header("Full Rankings Table", f"""
**Full Rankings Table**

All OD corridors sorted by the selected **Rank By** metric.{_filter_note}

> **Rank 1 = highest value.** For **Cost/Tonne**, Rank 1 is the most expensive corridor. To find the cheapest, sort ascending by clicking the column header.

**Column definitions:**
- **Tonnes** — annual road freight tonnes for selected commodity type(s)
- **Cost/Tonne** — total transport cost ÷ total tonnes (AUD/t)
- **Transport Cost** — total annual road transport cost (AUD)
- **Freight Value** — total value of goods transported (AUD)
- **CO₂** — total carbon dioxide equivalent emissions (t CO₂-e)
- **Avg Distance** — weighted average trip distance (km)

> Corridors with zero value for the selected commodity type(s) are included and sorted to the bottom.
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
        "orig_name":      "Origin",
        "orig_state":     "Orig State",
        "dest_name":      "Destination",
        "dest_state":     "Dest State",
        "tonnes":         "Tonnes",
        "cost_per_tonne": "Cost/Tonne ($)",
        "transport_cost": "Transport Cost ($)",
        "freight_value":  "Freight Value ($)",
        "co2":            "CO\u2082 (t)",
        "avg_distance":   "Avg Distance (km)",
        "trips":          "Trips",
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
        "dest_name":      "Destination",
        "dest_state":     "State",
        "tonnes":         "Tonnes",
        "cost_per_tonne": "Cost/Tonne ($)",
        "transport_cost": "Transport Cost ($)",
        "freight_value":  "Freight Value ($)",
        "co2":            "CO\u2082 (t)",
        "avg_distance":   "Avg Distance (km)",
        "trips":          "Trips",
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

st.dataframe(
    df_table,
    use_container_width=True,
    hide_index=True,
    height=420,
    column_config=col_config,
)

# CSV download
_filter_suffix = (
    "_filter_" + "_".join(sorted(industry_filter))
    if industry_filter else ""
)
csv_name = (
    f"rankings_by_industry_national_by_{rank_field}{_filter_suffix}.csv"
    if is_national
    else f"rankings_by_industry_{orig_code}_by_{rank_field}{_filter_suffix}.csv"
)
st.download_button(
    label="\u2b07 Download Rankings CSV",
    data=df_table.to_csv(index=False).encode("utf-8"),
    file_name=csv_name,
    mime="text/csv",
)

st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

# Back links at bottom
col_back1b, col_back2b, _ = st.columns([1, 1, 5])
with col_back1b:
    st.page_link("app.py", label="\u2190 OD Metrics", icon="\U0001f69b")
with col_back2b:
    st.page_link("pages/od_rankings.py", label="\u2190 All Types", icon="\U0001f4ca")
