# CSIRO TraNSIT Freight OD Explorer — CLAUDE.md

Standalone **2-page Streamlit app** for exploring Australian road freight data from the
CSIRO TraNSIT Benchmarking platform via its public REST API (no authentication required).
Built for freight analysts to understand what moves, where, at what cost, and how much CO₂.

---

## Run Command

```bash
# From repo root:
python -m streamlit run streamlit_cloud_app_csiro_freight_v2/CSIRO_TraNSIT_Dashboard.py

# Or from inside this folder:
streamlit run CSIRO_TraNSIT_Dashboard.py
```

---

## Folder Structure

```
streamlit_cloud_app_csiro_freight_v2/
├── CSIRO_TraNSIT_Dashboard.py     ← Page 1: OD Metrics + Charts
├── pages/
│   └── Commodity_OD_Rankings.py  ← Page 2: Commodity Rankings
├── api.py                         ← All API client + local data loaders
├── lga_codes.py                   ← 514 Australian LGAs (names, codes, states)
├── downloader.py                  ← Background download engine for local data
├── requirements.txt               ← streamlit>=1.35.0, pandas>=2.0.0, plotly>=5.0.0
├── CLAUDE.md                      ← This file
└── api_local_data/                ← Pre-downloaded local data (already populated)
    ├── level2/                    ← Industry-group data (groupBy_l2=true)
    │   ├── VIC/LGA_24600.json
    │   └── <STATE>/...
    └── level3/                    ← Individual commodity data (groupBy_l2=false)
        ├── VIC/LGA_24600.json
        └── <STATE>/...
```

Do NOT modify `app_with_visualisation/`.

---

## About the Data

### Is it annual? Yes.
All metrics represent **annual volumes and values** for one typical production year:
> *"The benchmarks model annual volumes and values, based on the most recent representative year."*

### Which year?
No single fixed year — CSIRO uses the most recent available data per commodity:
- Cattle & Sheep: 2022–2023 | Cotton: 2024 harvest
- General Freight & Beverages: 2021–2023 | Processed Food: 2023
- Mining: 2014/2015 base, updated 2024 | Grain: 2018 + 2024 silo volumes
- Vehicles: 2023 | Fuel: 2022 | Household Waste: 2018 | Forestry: 25-year average

### Can you filter by year?
**No.** The API has no year parameter (silently ignored). No year field in any response.

### Local data is already downloaded
`api_local_data/level2/` and `api_local_data/level3/` are pre-populated for all 8 states.
Users do NOT need to use the in-app download panel.

---

## Page 1 — CSIRO TraNSIT Dashboard (`CSIRO_TraNSIT_Dashboard.py`)

**Purpose:** Show all freight metrics for a selected Origin → Destination LGA pair.

### Sidebar Controls
- Origin State dropdown (default: VIC) → Origin LGA (default: Melbourne (C))
- Destination State → Destination LGA
- Transport Mode: Road / Rail / All Modes
  - Rail: blocked — commodityreport is road-only, shows error
  - All Modes: allowed but returns same data as Road (shows warning)
- LGA code chip shown below each selector
- Sidebar background: `#1E3A5F` (dark navy), text: `#C8DAF0`

### Session State Written (passed to Page 2)
- `shared_orig_code`, `shared_orig_name`, `shared_orig_state`
- `shared_dest_code`, `shared_dest_name`
- `orig_lga_name`, `dest_lga_name` (persist selection across rerenders)

### Main Content
1. **Route header** — `{Origin} [STATE_BADGE] {LGA_CODE} → {Dest} [STATE_BADGE] {LGA_CODE}`
2. **API endpoint expander** — shows full URL used
3. **10 Headline Metric Cards** (2 rows × 5 columns):
   - Annual Tonnes, Annual Trailers, Cost per Tonne, Total Transport Costs,
     Total Freight Value, Total Travel Distance (km), Annual Tonne-km,
     Avg Trip Distance (km), Avg Trip Duration (hrs), Total CO₂ (t)
4. **Industry Breakdown Table** — per industry group (Level 2); TOTAL row at bottom;
   columns: Industry, Sector, Trips, Tonnes, Trailers, Transport Cost ($), Freight Value ($),
   Cost/t ($), Tonne-km, Total Distance (km), CO₂ (t); CSV download buttons
5. **4 Freight Profile Charts** (2×2 grid, each with ⓘ info popover):
   - **A1** Trip Length Distribution — grouped bar: Short/Medium/Long × sector, toggleable Tonnes/Trips
   - **A2** Supply Chain Flows — horizontal bar, orig_type → dest_type sorted by tonnes
   - **A3** Transport Cost Breakdown — stacked horizontal bar by cost component
     (Capital/Driver/Fuel/Fixed/Maintenance/Load/Unload); **total annual AUD**, not per-tonne
   - **B4** Freight Composition by Industry — donut, hole=0.45, total tonnes in centre
6. **"Go to Commodity OD Rankings →"** navigation link to Page 2
7. **Raw JSON expander** — full API response

---

## Page 2 — Commodity OD Rankings (`pages/Commodity_OD_Rankings.py`)

**Purpose:** Rank freight corridors by individual commodity flows (Level 3 data).

### Sidebar Controls

**Scope** (radio):
- `🌏 All Origins — National` — loads all local data, shows top corridors nationally
- `📍 Single Origin` — all destinations from one selected origin

**Origin selector** (Single Origin only): State + LGA dropdowns (independent from Page 1)

**Filter by Origin State** multiselect (National scope only)

**Data Source** (Single Origin only):
- `📶 Online (API)` — uses `densitymap` endpoint, fast, no commodity filtering possible
- `💾 Local Data` — uses `api_local_data/level3/`, supports all commodity filters

**National scope always uses Local Data.**

**Rank By**: Tonnes / Cost/Tonne (AUD) / Transport Cost ($) / CO₂ (t) / Trips
- **Rank 1 = highest value.** For Cost/Tonne, Rank 1 = most expensive corridor.
- Stored in `rank_metric` (str); mapped to `rank_field` and `(axis_label, fmt_str)` via:

```python
_RANK_FIELD_MAP  = {"Tonnes": "tonnes", "Cost/Tonne (AUD)": "cost_per_tonne",
                    "Transport Cost ($)": "transport_cost", "CO₂ (t)": "co2", "Trips": "trips"}
_RANK_LABEL_MAP  = {"Tonnes": ("Tonnes",",.0f"), "Cost/Tonne (AUD)": ("Cost/Tonne (AUD)","$,.2f"),
                    "Transport Cost ($)": ("Transport Cost ($)","$,.0f"),
                    "CO₂ (t)": ("CO₂ (t)",",.1f"), "Trips": ("Trips",",.0f")}
rank_field = _RANK_FIELD_MAP[rank_metric]
axis_label, fmt_str = _RANK_LABEL_MAP[rank_metric]
```

**Commodity Filter** (two categories, Local Data only):

| Category | Filter Type | What it selects |
|---|---|---|
| 📡 TraNSIT API | 🌐 All Commodities | Pick specific commodity names from L3 data |
| 📡 TraNSIT API | 🏭 By Industry Group (L2) | Select industry groups (food, livestock, etc.) |
| ⚙️ User-Defined Groups | 📂 By Sector | Curated sectors: beverage, cold_food, general, health, horticulture |
| ⚙️ User-Defined Groups | 🏷️ By Industry | Curated industries: alcohol_beverage, dairy_product, meat, medicines, seafood, etc. |

---

## Rank By Responsiveness — Which Charts Are Dynamic

| Chart | Responds to Rank By? | Notes |
|---|---|---|
| **R1** Top 20 National OD Corridors | ✅ YES | x-axis, sort, title, hover — all dynamic |
| **R1** Top 15 Single Origin Destinations | ✅ YES | Same |
| **R4** Full Rankings Table | ✅ YES | DataFrame sorted by `rank_field` |
| **Chart A** Commodity Share | ✅ YES | `_comm_rows` re-sorted by `rank_field`; x-axis = `rank_field` |
| **Chart 3** Top 10 OD Corridors by Commodity | ✅ YES | `_render_corridor_bar()` re-sorts corridors + uses `rank_field` |
| **B3** Top Origins & Top Destinations | ✅ YES | Aggregates by `rank_field`; title, x-axis, hover all dynamic |
| **B1** 3rd summary card | ✅ YES | Label + value change: "Median Trips", "Median CO₂", etc. |
| **Chart B** Cost vs Volume scatter | ✅ BY DESIGN | Fixed 2D view (X=tonnes, Y=cost/tonne) — always a reference chart |
| **Chart 2** Freight Value-to-Cost Ratio | ✅ BY DESIGN | Fixed: shows value/cost ratio always |
| **B7** Freight Value vs Tonnes scatter | ✅ BY DESIGN | Fixed 2D exploratory chart |
| **R3** CO₂ vs Transport Cost scatter | ✅ BY DESIGN | Fixed 2D exploratory chart |
| **B2** State-to-State Heatmap | ✅ BY DESIGN | Always shows tonne flows between state pairs |
| **B4** Intra vs Inter-state | ✅ BY DESIGN | Always shows volume split in tonnes |
| **B5** Cost/Tonne Distribution by State | ✅ BY DESIGN | Always shows cost/tonne box plot |

---

## Charts — National Scope

- **B1** Summary Cards — OD Corridors, Total Tonnes, **Median [rank_metric]** (dynamic), Total CO₂, Origins with Data
- **B2** State-to-State Freight Flow Heatmap (`go.Heatmap`) — always tonnes
- **R1** Top 20 National OD Corridors — horizontal bar, x-axis = `rank_field`, coloured by origin state
- **B3** Top Origins & Top Destinations — side-by-side horizontal bars (top 10 each), x-axis = `rank_field`, title includes rank metric
- **B4** Intra-state vs Inter-state Split — donut + stacked bar per state (always tonnes)
- **B5** Cost per Tonne Distribution by State — box plot per state (always cost/tonne)
- **B7** Freight Value vs Tonnes scatter — per-state coloured dots, median crosshairs
- **R3** CO₂ vs Transport Cost scatter
- **R4** Full Rankings Table + CSV download

## Charts — Single Origin Scope

- **R1** Top 15 Destinations — horizontal bar, x-axis = `rank_field`, orange = Page 1 selection
- **B7** Freight Value vs Tonnes scatter — orange = selected dest, grey = others
- **R3** CO₂ vs Transport Cost scatter — orange = selected dest, grey = others
- **R4** Full Rankings Table + CSV download

---

## Commodity Filter Insights Section (Page 2)

**Trigger:** Active only when Commodity Filter is on AND data source is Local Data
(`if (industry_filter or commodity_filter) and not is_online`).

**Position:** Between data source info note and main ranking charts (B1/R1 etc.).

**Data source:** `_cached_commodity_summary()` → `_load_commodity_summary_l3_filtered()`
aggregates raw Level 3 JSON **per commodity name** (not per OD pair).

### Layout

```
🔬 COMMODITY FILTER INSIGHTS  [ⓘ▾]
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Commodities  │ Total Tonnes │ Avg Cost/t   │ Total CO₂    │  ← 4 fixed metric cards
└──────────────┴──────────────┴──────────────┴──────────────┘
[Chart A: Commodity Share by {rank_metric}] │ [Chart B: Cost vs Volume (fixed)]
─────────────────────────────────────────────────────────────
[Chart 1: Multi-Metric Comparison Table — full width]
[Chart 2: Freight Value-to-Cost Ratio — full width]
[Chart 3: Top 10 OD Corridors by Commodity — tabbed, full width]
─────────────────────────────────────────────────────────────
```

### Component Details

**4 Summary Metric Cards** (fixed — not rank-responsive):
- Commodities Matched, Total Tonnes, Avg Cost/Tonne, Total CO₂

**`_comm_rows` re-sort (before Chart A):**
```python
_comm_rows = sorted(_comm_rows, key=lambda r: r[rank_field], reverse=True)
```
This single line propagates the Rank By selection to Chart A, Chart 1 (table row order),
and Chart 3 (tab order). Raw load order from `_cached_commodity_summary()` is always
tonnes-desc, so this re-sort is required.

**Chart A — Commodity Share by {rank_metric}** (`section=False`, left column):
- Title is f-string: `f"Commodity Share by {rank_metric}"`
- `go.Bar(orientation="h")`, sorted by `rank_field` desc, max 20 bars
- `x=[r[rank_field] for r in _ci_top20]`, `xaxis_title=axis_label`
- `hovertemplate`: `f"{axis_label}: %{{x:{fmt_str}}}"` + weighted avg cost/tonne
- Bar colour = `_INDUSTRY_COLORS[industry]`
- HTML colour chip legend below chart

**Chart B — Cost vs Volume by Commodity** (`section=False`, right column):
- **Fixed** — always X=tonnes, Y=cost_per_tonne regardless of Rank By
- `go.Scatter(mode="markers+text")`
- Dot size proportional to CO₂: `max(8, min(40, co2/max_co2 * 40))`
- Only rendered when `len(_comm_rows) >= 2`
- Caption: "Dot size proportional to CO₂ emissions · Coloured by industry group"

**Chart 1 — Multi-Metric Commodity Comparison** (full width):
- `st.dataframe()` columns: Commodity, Industry, Tonnes, Cost/Tonne ($), CO₂/Tonne (kg),
  Load Factor (t/trip), OD Pairs, Total CO₂ (t)
- Row order follows `_comm_rows` (already sorted by `rank_field`)
- Pinned **TOTAL / WEIGHTED AVG** row at bottom
- `st.download_button` → `commodity_comparison.csv`

**Chart 2 — Freight Value-to-Cost Ratio** (full width):
- **Fixed** — always shows `freight_value / transport_cost`
- `go.Bar(orientation="h")`, sorted by ratio desc
- Colour gradient: amber → green by ratio
- `r.get("freight_value", 0.0)` used to handle stale cache gracefully

**Chart 3 — Top 10 OD Corridors by Commodity** (full width):
- `st.tabs()` for ≤8 commodities; `st.selectbox()` for >8
- Tab order follows `_comm_rows` sort (i.e. `rank_field` order)
- Each tab calls `_render_corridor_bar(corridors, comm_key, rank_field, axis_label, fmt_str)`
- Bars sorted by `rank_field` inside `_render_corridor_bar()`
- Bar colour = `STATE_COLORS[dest_state]`
- **Known limitation:** Corridors are pre-loaded as top-10 by tonnes (cached loader).
  When a different rank metric is selected, bars re-order within those 10 corridors.
  Routes outside the top-10 by tonnes will not appear even if they rank higher by the
  selected metric (e.g. Trips or CO₂).

---

## Internal Functions — Page 2 (`Commodity_OD_Rankings.py`)

### `_render_corridor_bar()` — updated signature

```python
def _render_corridor_bar(
    corridors: list[dict],
    comm_key: str,
    rank_field: str = "tonnes",
    axis_label: str = "Annual Tonnes",
    fmt_str: str = ",.0f",
) -> None:
    """
    Render a Top-10 OD corridor horizontal bar chart for one commodity.
    Sorts corridors by rank_field desc before plotting.
    Called inside each st.tab or after st.selectbox for Chart 3.
    """
```

Key behaviour:
- `corridors = sorted(corridors, key=lambda r: r[rank_field], reverse=True)` — re-sorts on render
- `x=[r[rank_field] for r in corridors]` — dynamic x-axis
- `xaxis_title=axis_label` — dynamic axis label

### `_b3_agg()` — inline helper for B3 aggregation

Defined inline inside the `if is_national:` block:

```python
def _b3_agg(group_cols: list[str], val_col: str) -> tuple:
    """
    Aggregate df by rank_field for B3 (Top Origins / Top Destinations).
    Handles cost_per_tonne as a ratio (SUM(transport_cost)/SUM(tonnes))
    rather than a summable field.
    Returns (df_top10, list_of_values).
    """
    if rank_field == "cost_per_tonne":
        _agg = df.groupby(group_cols).agg(_tc=("transport_cost","sum"), _t=("tonnes","sum")).reset_index()
        _agg["_rank_val"] = _agg["_tc"] / _agg["_t"].replace(0, float("nan"))
        _top = _agg.nlargest(10, "_rank_val")
        return _top, _top["_rank_val"].tolist()
    else:
        _agg = df.groupby(group_cols)[rank_field].sum().reset_index()
        _top = _agg.nlargest(10, rank_field)
        return _top, _top[rank_field].tolist()
```

### Per-commodity summary loader

```python
def _load_commodity_summary_l3_filtered(
    industry_filter, commodity_filter,
    orig_lga=None, orig_state_arg=None,
    state_filter: frozenset | None = None,   # ← national scope only
) -> tuple[list[dict], str | None]:
    """
    Aggregate Level 3 JSON per COMMODITY NAME (not per OD pair).
    Raw load always sorts by tonnes desc. Re-sort by rank_field happens at render time.
    state_filter: when provided (national scope), only scans JSON files for those states.
    Returns list of dicts with:
        commodity_key, commodity_display, industry, sector,
        tonnes, transport_cost, freight_value, co2, trips, od_pairs, cost_per_tonne
    """

@st.cache_data(show_spinner=False)
def _cached_commodity_summary(
    ...,
    state_filter_frozen: frozenset = frozenset(),  # ← NEW; hashable for cache key
) -> tuple[list[dict], str | None]:
    """Cached wrapper. Does NOT receive rank_field — sort happens after retrieval.
    state_filter_frozen forwarded as state_filter=state_filter_frozen or None."""
```

### Per-commodity corridor loader

```python
def _load_commodity_od_corridors_l3_filtered(
    industry_filter, commodity_filter,
    orig_lga=None, orig_state_arg=None,
    state_filter: frozenset | None = None,   # ← national scope only
) -> tuple[dict[str, list[dict]], str | None]:
    """
    Aggregate per (commodity_key, orig_lga, dest_lga) triple.
    PRE-SORTED by tonnes desc, SLICED to top 10 per commodity at load time.
    Re-sort by rank_field happens inside _render_corridor_bar() at render time.
    state_filter: when provided (national scope), only scans JSON files for those states.
    Returns {commodity_key: [top10 corridor dicts]}.
    Each corridor dict: orig_lga, dest_lga, orig_name, dest_name,
                        orig_state, dest_state, tonnes, transport_cost,
                        cost_per_tonne, co2, trips
    """

@st.cache_data(show_spinner=False)
def _cached_commodity_od_corridors(
    ...,
    state_filter_frozen: frozenset = frozenset(),  # ← NEW; hashable for cache key
) -> tuple[dict[str, list[dict]], str | None]:
    """Cached wrapper. state_filter_frozen forwarded as state_filter=... or None."""
```

### Existing filtered loaders

```python
_load_all_od_pairs_l3_filtered(industry_filter, commodity_filter) → (rows, error)
_load_local_origin_l3_filtered(orig_lga, orig_state, industry_filter, commodity_filter) → (rows, error)
_cached_od_pairs_l3(industry_filter_frozen, commodity_filter_frozen) → (rows, error)
_cached_local_origin_l3(orig_lga, orig_state, industry_filter_frozen, commodity_filter_frozen) → (rows, error)
```

---

## API (`api.py`)

**Base:** `https://benchmark.transit.csiro.au/api/benchmarking`
**Dataset:** `SIM-AU-BASELINE` (always fixed — do not change)

### Endpoints

| Function | Endpoint | Key Params | Returns |
|---|---|---|---|
| `fetch_od_metrics()` | `commodityreport` | orig_lga, dest_lga, mode=road, groupBy_l2=true | industry records + totals |
| `fetch_trip_length()` | `triplengthreport` | orig_lga, dest_lga, mode | trip type distribution |
| `fetch_supply_chain()` | `supplychainreport` | orig_lga, dest_lga, mode | supply chain flows |
| `fetch_logistics()` | `transportlogisticsreport` | orig_lga, dest_lga, mode | cost component breakdown |
| `fetch_origin_destinations()` | `densitymap` | orig_lga, mode | all destinations from origin |

### `_compute_totals()` — aggregates records into headline metrics

| Output Field | Formula |
|---|---|
| `annual_tonnes` | SUM(tonnes) |
| `annual_trailers` | SUM(trailer_loads) |
| `cost_per_tonne` | SUM(trip_transport_costs) / SUM(tonnes) |
| `total_transport_costs` | SUM(trip_transport_costs) |
| `total_freight_value` | SUM(total_freight_value) |
| `total_travel_distance_km` | SUM(total_trip_distance) |
| `annual_tonne_km` | SUM(tonne_kms) |
| `avg_trip_distance_km` | trip-weighted average of avg_trip_distance |
| `avg_trip_duration_hrs` | trip-weighted average of avg_trip_duration |
| `total_co2_t` | SUM(co2_tn) |
| `total_trips` | SUM(trips_count) |

When `orig_lga == dest_lga` (local trip): `avg_trip_distance_km` and `avg_trip_duration_hrs` → 0.

### Local Data Paths
```python
LOCAL_DATA_ROOT    = Path(__file__).parent / "api_local_data" / "level2"
LOCAL_DATA_ROOT_L3 = Path(__file__).parent / "api_local_data" / "level3"
```

### Local Data File Format
```json
{
  "orig_lga": "LGA_24600",
  "orig_name": "Melbourne (C)",
  "orig_state": "VIC",
  "fetched_at": "2026-03-12T06:45:59+00:00",
  "destinations": {
    "LGA_24600": [commodity_records...],
    "LGA_21180": [commodity_records...]
  }
}
```

---

## LGA Data (`lga_codes.py`)

- **514 Australian LGAs** across 8 states/territories
- `LGA_CODES`: `{LGA_code: display_name}`
- `LGA_NAMES`: `{display_name: LGA_code}` (reverse lookup)
- `LGA_STATE`: `{LGA_code: state_abbr}` e.g. `"LGA_24600" → "VIC"`
- `STATE_LGAS`: `{state: [sorted_LGA_names]}`
- `STATE_COLORS`: `{state: hex_color}` for state badges and charts

LGA code → state: first digit after `LGA_` prefix:
`1=NSW, 2=VIC, 3=QLD, 4=SA, 5=WA, 6=TAS, 7=NT, 8=ACT`

---

## Downloader (`downloader.py`)

Background thread. **Local data already downloaded — users should not need this.**

```python
start_download_l3(state_filter="VIC", force=False)
cancel_download_l3()
get_progress_l3()  → DownloadProgress singleton
```

---

## Design System

### Colours
| Token | Hex | Use |
|---|---|---|
| `_BLUE` | `#2563EB` | Default bars, metric card border |
| `_ORANGE` | `#F97316` | Selected destination highlight |
| `_GREEN` | `#10B981` | Cost/efficiency |
| `_RED` | `#DC2626` | CO₂, high-cost |
| `_PURPLE` | `#7C3AED` | Distance, maintenance |
| `_AMBER` | `#D97706` | Freight value, unload cost |
| `_TEAL` | `#0D9488` | Fixed cost, transport |
| `_INDIGO` | `#4F46E5` | Trailers, driver cost |
| `_GREY` | `rgba(37,99,235,0.55)` | Non-selected dots in scatter charts |

Sidebar: background `#1E3A5F`, text `#C8DAF0`, dividers `#2E5A8C`

### `_INDUSTRY_COLORS` (Page 2, 25 entries)

| Industry | Colour |
|---|---|
| food | `#10B981` | livestock | `#F97316` | medicines | `#DC2626` |
| vehicles | `#4F46E5` | waste | `#9CA3AF` | seafood | `#0D9488` |
| beverage | `#2563EB` | alcohol_beverage | `#1D4ED8` | fuel | `#D97706` |
| viticulture | `#7C3AED` | grains | `#A16207` | meat | `#EF4444` |
| dairy_product | `#0EA5E9` | fruit | `#F59E0B` | vegetables | `#16A34A` |
| horticulture | `#34D399` | chemicals | `#6B7280` | fibre | `#A3E635` |
| sugar | `#FCD34D` | wood_product | `#92400E` | nuts | `#78350F` |
| tissue_product | `#BAE6FD` | ppe | `#E879F9` | household_general | `#6B7280` |
| other_retail_ess | `#9CA3AF` | | |

Fallback: `_BLUE`.

### Plotly Layout
```python
_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
```
Page 2 omits `margin` from `_PLOTLY_LAYOUT` and sets it per-chart.

### `chart_header()` Helper (defined in both files)
```python
def chart_header(title: str, info_md: str, section: bool = True) -> None:
    """Render title + clickable ⓘ info popover in a [0.88, 0.12] column layout."""
```
- `section=True` → grey uppercase 11px section label
- `section=False` → bold 14px chart title
- Many info_md strings are f-strings using `rank_metric` for dynamic popover text

---

## Session State Keys

| Key | Set by | Used by | Purpose |
|---|---|---|---|
| `shared_orig_code` | Page 1 sidebar | Page 2 | Pass origin LGA code |
| `shared_orig_name` | Page 1 sidebar | Page 2 | Pass origin name |
| `shared_orig_state` | Page 1 sidebar | Page 2 | Pass state abbreviation |
| `shared_dest_code` | Page 1 sidebar | Page 2 | Highlight dest on Page 2 |
| `shared_dest_name` | Page 1 sidebar | Page 2 | Highlight dest name |
| `orig_lga_name` | Page 1 sidebar | Page 1 | Persist origin across rerenders |
| `dest_lga_name` | Page 1 sidebar | Page 1 | Persist dest across rerenders |
| `l3_orig_state` | Page 2 sidebar | Page 2 | Origin state on Page 2 |
| `l3_orig_lga_name` | Page 2 sidebar | Page 2 | Origin LGA on Page 2 |
| `comm_corr_select` | Page 2 body | Page 2 | Selectbox key for Chart 3 (>8 commodities) |

---

## Known Behaviours / Edge Cases

- **No year filtering:** API has no year parameter; data represents annual totals (~2021–2024).
- **Rail unavailable:** `commodityreport` is road-only. Selecting Rail shows an error.
- **All Modes = Road:** Same data returned; a warning note is shown.
- **Suppressed data:** OD pairs with <5 movements return empty list. App shows a graceful info message.
- **densitymap ≠ commodityreport:** Different pipelines — numbers differ for the same OD pair.
  Page 2 Online mode shows a disclaimer. Use Local Data for numbers consistent with Page 1.
- **Rank 1 = highest value** for ALL metrics including Cost/Tonne (most expensive = Rank 1).
- **A3 Transport Cost Breakdown:** Displays total annual AUD (not per tonne).
- **B1 Median card may show $0.00 or 0:** When a commodity filter is active and many corridors
  have no data for the selected commodity (suppressed by CSIRO), the unweighted median across
  all corridors is 0. This is correct but potentially misleading. The info popover explains this.
- **Commodity filter disabled in Online mode:** Requires Local Data.
- **Commodity Filter Insights disabled in Online mode:** Section guarded by `not is_online`.
- **Commodity Filter Insights responds to state filter:** `_cached_commodity_summary()` and
  `_cached_commodity_od_corridors()` accept `state_filter_frozen: frozenset`. When national
  scope, call sites pass `frozenset(state_filter)`. The loaders filter `json_files` by
  `f.parent.name in state_filter` before scanning. Empty frozenset = all states.
- **Stale Streamlit cache:** `_cached_commodity_summary` may return old dicts without `freight_value`
  after a code update. Chart 2 uses `r.get("freight_value", 0.0)` to handle this gracefully.
- **Chart 3 top-10 pre-selection:** Corridors are pre-loaded as top-10 by tonnes (cached).
  When rank_field ≠ "tonnes", bars re-order within those 10. Routes outside top-10 by tonnes
  will not appear even if they rank higher by the selected metric.
- **Local data already downloaded:** All 8 states in `api_local_data/`. Download panel is present
  but users should not need it.
- **`_render_corridor_bar` defined before `_PLOTLY_LAYOUT`:** Safe — Python resolves global
  names at call time, not definition time.
- **`_b3_agg` defined inside `if is_national:` block:** Inline helper function, not reusable
  outside that block. Defined at render time with `rank_field` in closure.

---

## Quick Reference — Adding New Charts

1. Add fetch function to `api.py` using `_od_fetch(endpoint, orig, dest, mode)`
2. Add cached wrapper in `CSIRO_TraNSIT_Dashboard.py`: `@st.cache_data(show_spinner=False)`
3. Use `chart_header(title, info_md, section=False)` for chart title + ⓘ popover
4. Build: `fig = go.Figure()` → `fig.update_layout(**_PLOTLY_LAYOUT, ...)` → `st.plotly_chart(fig, use_container_width=True)`
5. To make the chart rank-responsive: use `rank_field` for x-axis/sort, `axis_label` for title, `fmt_str` for hover

## Quick Reference — Adding Commodity Groups (User-Defined)

Edit `_SECTOR_DICT` and/or `_INDUSTRY_DICT` at the top of `pages/Commodity_OD_Rankings.py`.
Keys are snake_case commodity identifiers matching `_normalize(commodity_name_from_api)`.
Add display overrides to `_COMMODITY_DISPLAY_OVERRIDES` if the auto-title-case is wrong.

---

## Dependencies

```
streamlit>=1.35.0
pandas>=2.0.0
plotly>=5.0.0
```

---

## Changes Log (Current Session)

### Rank By Responsiveness Fixes

**Charts made dynamic (Commodity Filter Insights):**
- **Chart A** — title, x-axis, xaxis_title, hovertemplate now use `rank_field`/`axis_label`/`fmt_str`
- **Chart 3** — `_render_corridor_bar()` signature extended to accept rank params; re-sorts corridors by `rank_field`; tab order follows `_comm_rows` sort

**Charts made dynamic (National scope):**
- **B3 Top Origins & Top Destinations** — both charts now use `_b3_agg()` helper to aggregate by `rank_field`; chart titles, x-axis titles, and hover all dynamic; cost_per_tonne handled as ratio (SUM(transport_cost)/SUM(tonnes)) not a sum
- **B1 3rd summary card** — label and value now reflect selected rank_metric:
  - Tonnes → "Median Tonnes" in `t`
  - Cost/Tonne → "Median Cost/Tonne" in `$`
  - Transport Cost → "Median Transport Cost" in `$`
  - CO₂ → "Median CO₂ (t)"
  - Trips → "Median Trips"

### Info Popover Improvements

**Page 2:**
- Chart B — added "fixed by design" note; replaced `∝` with "proportional to" in caption
- Chart 1 — Load Factor explained in plain English; TOTAL row clarifies sums vs weighted averages
- Chart 3 — added pre-selection limitation note; tab order behaviour documented
- B7 caption — `∝` → "proportional to"
- R3 info_md — all 4 quadrants now explained; `∝` → "proportional to" in caption
- B1 popover — updated to mention that the Median card reflects the selected Rank By metric; added $0.00 explanation

**Page 1:**
- "Freight Profile Charts" section — full rewrite with plain-English description of each chart's purpose
- Inline helper text — updated from vague "replicating" to descriptive text
- A1 Trip Length — added "What to look for" interpretation block
- OD Corridor Rankings — added Tip about Local Data mode matching Page 1 numbers

### State Filter Responsiveness Fix (Commodity Filter Insights)

**Root cause:** `_load_commodity_summary_l3_filtered()` and `_load_commodity_od_corridors_l3_filtered()`
scanned ALL state directories regardless of the "Filter by Origin State" selection.

**Fix:** Added `state_filter: frozenset | None = None` to both loaders and
`state_filter_frozen: frozenset = frozenset()` to both cached wrappers. National scope
call sites now pass `frozenset(state_filter) if state_filter else frozenset()`. Loaders
filter `json_files` to selected states via `f.parent.name in state_filter`.

**Scope:** Single Origin scope does not pass `state_filter` (defaults to `frozenset()` = all).
`frozenset` is used (not `list`) because `@st.cache_data` requires hashable arguments.
