"""
utils.py — Shared utilities for localis_sampledata_passenger_app
CSS injection, HTML builders, formatters, data loaders, color constants.
"""

import os
import re

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
C_NAVY   = "#1e3a5f"
C_BLUE   = "#3b82f6"
C_SKY    = "#93c5fd"
C_ORANGE = "#f97316"
C_GRID   = "#f1f5f9"
C_BORDER = "rgba(49,51,63,0.10)"

# ---------------------------------------------------------------------------
# A — CSS injection
# ---------------------------------------------------------------------------

def inject_css() -> None:
    """Inject shared CSS for kpi-card, info-card, badge-card, block-container."""
    st.markdown("""
<style>
    .block-container {
        max-width: 1440px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }
    .kpi-tile {
        background: #ffffff;
        border: 1px solid rgba(49,51,63,0.09);
        border-radius: 14px;
        padding: 1rem 1.15rem 0.9rem 1.15rem;
        min-height: 92px;
    }
    .kpi-card {
        padding: 0.85rem 0.95rem 0.8rem 0.95rem;
        border: 1px solid rgba(49,51,63,0.11);
        border-radius: 14px;
        background: white;
        min-height: 90px;
    }
    .kpi-label {
        font-size: 0.73rem;
        color: rgba(49,51,63,0.55);
        font-weight: 500;
        margin-bottom: 0.22rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    .kpi-value { font-size: 1.85rem; font-weight: 700; color: #1e3a5f; line-height: 1.1; }
    .kpi-sub   { font-size: 0.76rem; color: rgba(49,51,63,0.45); margin-top: 0.15rem; }
    .sec-header { font-size: 0.95rem; font-weight: 650; color: #1e3a5f; margin-bottom: 0.45rem; }
    .section-title {
        font-size: 1.45rem;
        font-weight: 700;
        color: rgb(36,41,46);
        margin-top: 0.2rem;
        margin-bottom: 0.2rem;
    }
    .section-subtitle {
        font-size: 0.95rem;
        color: rgba(49,51,63,0.72);
        margin-bottom: 0.9rem;
    }
    .subsection-title {
        font-size: 1rem;
        font-weight: 650;
        color: rgb(36,41,46);
        margin-bottom: 0.6rem;
    }
    .soft-panel {
        padding: 1rem 1rem 0.75rem 1rem;
        border: 1px solid rgba(49,51,63,0.10);
        border-radius: 14px;
        background: rgba(252,252,253,1);
        margin-bottom: 0.9rem;
    }
    .info-card {
        padding: 0.72rem 0.9rem;
        border: 1px solid rgba(49,51,63,0.10);
        border-radius: 12px;
        background: rgba(250,250,252,1);
        margin-bottom: 0.55rem;
    }
    .info-label {
        font-size: 0.74rem;
        color: rgba(49,51,63,0.64);
        margin-bottom: 0.18rem;
        font-weight: 500;
    }
    .info-value { font-size: 0.95rem; color: rgb(36,41,46); font-weight: 600; }
    .badge-card {
        padding: 0.72rem 0.85rem;
        border: 1px solid rgba(49,51,63,0.10);
        border-radius: 12px;
        background: white;
        text-align: center;
        min-height: 74px;
        margin-bottom: 0.55rem;
    }
    .badge-label {
        font-size: 0.72rem;
        color: rgba(49,51,63,0.64);
        margin-bottom: 0.18rem;
        font-weight: 500;
    }
    .badge-value { font-size: 1rem; color: rgb(36,41,46); font-weight: 700; }
    .chart-note {
        font-size: 0.88rem;
        color: rgba(49,51,63,0.72);
        margin-bottom: 0.55rem;
        padding-top: 0.45rem;
    }
    div[data-testid="stDownloadButton"] > button {
        width: 100%;
        border-radius: 10px;
        min-height: 42px;
        font-size: 0.85rem;
    }
    div[data-testid="stExpander"] {
        border: 1px solid rgba(49,51,63,0.10);
        border-radius: 12px;
        background: white;
    }
    div[data-testid="stTabs"] button { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# B — HTML builders
# ---------------------------------------------------------------------------

def kpi_tile_html(label: str, value: str, sub: str = "") -> str:
    """KPI tile used in App 1 (OD Overview) top row."""
    return (
        f'<div class="kpi-tile">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f'</div>'
    )


def build_kpi_html(label: str, value: str) -> str:
    """KPI card used in App 2 (Corridor Detail)."""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """


def build_info_html(label: str, value: str) -> str:
    return f"""
    <div class="info-card">
        <div class="info-label">{label}</div>
        <div class="info-value">{value}</div>
    </div>
    """


def build_badge_html(label: str, value: str) -> str:
    return f"""
    <div class="badge-card">
        <div class="badge-label">{label}</div>
        <div class="badge-value">{value}</div>
    </div>
    """


def chart_header(title: str, info_md: str, h3: bool = False) -> None:
    """Render a section header with an inline ℹ popover info button.

    h3=True  → uses ### markdown heading (pages 3 & 4 style)
    h3=False → uses sec-header CSS class (pages 1 & 2 style, requires inject_css)
    """
    col_t, col_i = st.columns([0.92, 0.08])
    with col_t:
        if h3:
            st.markdown(f"### {title}")
        else:
            st.markdown(f'<div class="sec-header">{title}</div>', unsafe_allow_html=True)
    with col_i:
        with st.popover("ℹ"):
            st.markdown(info_md)


# ---------------------------------------------------------------------------
# C — Formatting helpers
# ---------------------------------------------------------------------------

def format_percent(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def format_distance(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.1f} km"


def format_int(value) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{int(value):,}"


def format_coord(lat_value, lon_value) -> str:
    if pd.isna(lat_value) or pd.isna(lon_value):
        return "N/A"
    return f"{lat_value:.4f}, {lon_value:.4f}"


def get_first_value(df: pd.DataFrame, col: str, default=None):
    if col in df.columns and not df.empty:
        return df[col].iloc[0]
    return default


def safe_filename(text: str) -> str:
    text = str(text).strip().replace(" ", "_")
    text = re.sub(r"[^\w\-.]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("_-")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# D — Data loaders (for Apps 1 & 2 which use pre-built pipeline CSVs)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Loading corridor data...")
def load_ranked_and_temporal(ranked_path: str, temporal_path: str):
    """Load ranked_corridors.csv and temporal_distribution_all.csv.
    Returns (ranked_df, temporal_df, error_message_or_None).
    """
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
