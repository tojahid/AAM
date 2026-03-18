# CSIRO TraNSIT Freight OD Explorer — CLAUDE.md

Standalone **2-page Streamlit app** for exploring Australian road freight data from the
CSIRO TraNSIT Benchmarking platform via its public REST API (no authentication required).
Built for freight analysts to understand what moves, where, at what cost, and how much CO₂.

---

## Run Command

```bash
# From repo root:
python -m streamlit run streamlit_cloud_app_csiro_freight/CSIRO_TraNSIT_Dashboard.py

# Or from inside this folder:
streamlit run CSIRO_TraNSIT_Dashboard.py
```

---

## Folder Structure

```
streamlit_cloud_app_csiro_freight/       ← THIS IS THE ACTIVE DEPLOYMENT FOLDER
├── CSIRO_TraNSIT_Dashboard.py           ← Page 1: OD Metrics + Charts (1081 lines)
├── pages/
│   └── Commodity_OD_Rankings.py         ← Page 2: Commodity Rankings (1710 lines)
├── api.py                               ← All API client + local data loader functions (418 lines)
├── lga_codes.py                         ← 514 Australian LGAs (names, codes, states)
├── downloader.py                        ← Background download engine for local data
├── requirements.txt                     ← streamlit>=1.35.0, pandas>=2.0.0, plotly>=5.0.0
└── api_local_data/                      ← Pre-downloaded local data (already populated)
    ├── level2/                          ← Industry-group data (groupBy_l2=true)
    │   ├── VIC/LGA_24600.json           ← One JSON file per origin LGA
    │   ├── NSW/...
    │   └── <STATE>/...
    └── level3/                          ← Individual commodity data (groupBy_l2=false)
        ├── VIC/LGA_24600.json
        └── <STATE>/...
```

The parent folder also has `app_with_visualisation/` — an older reference version. Do NOT
modify it. The active working folder is `streamlit_cloud_app_csiro_freight/`.

---

## About the Data

### Is it annual? Yes.
All metrics (tonnes, costs, CO₂, trailers, etc.) represent **annual volumes and values**
for one typical production year, per the official CSIRO FAQ:
> *"The benchmarks model annual volumes and values, based on the most recent representative year."*

### Which year?
There is **no single fixed year** — CSIRO uses the most recent available data per commodity:
- Cattle & Sheep: 2022–2023
- Cotton: 2024 harvest
- General Freight & Beverages: 2021–2023
- Processed Food (boxed beef, chicken, lamb): 2023
- Mining: 2014/2015 base, updated 2024
- Grain: 2018 locations + 2024 silo volumes
- Vehicles: 2023 | Fuel: 2022 | Household Waste: 2018
- Forestry: 25-year rotation average

### Can you filter by year?
**No.** The API has no year parameter (tested — silently ignored). No year field exists in
any API response. Year-on-year comparison is not supported by the platform.

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
Exposes individual commodity names (e.g. Beer, Wheat, Barramundi, PBS Medicines).

### Sidebar Controls

**Scope** (radio):
- `🌏 All Origins — National` — loads all local data, shows top corridors nationally
- `📍 Single Origin` — all destinations from one selected origin

**Origin selector** (Single Origin only): State + LGA dropdowns (independent from Page 1)

**Filter by Origin State** multiselect (National scope only)

**Data Source** (Single Origin only):
- `📶 Online (API)` — uses `densitymap` endpoint, fast, no commodity filtering possible
- `💾 Local Data` — uses `api_local_data/level3/`, supports all commodity filters

**National scope always uses Local Data** — online API cannot do multi-origin queries.

**Rank By**: Tonnes / Cost/Tonne (AUD) / Transport Cost ($) / CO₂ (t) / Trips
- **Rank 1 = highest value.** For Cost/Tonne, Rank 1 = most expensive corridor.

**Commodity Filter** (two categories, Local Data only):

| Category | Filter Type | What it selects |
|---|---|---|
| 📡 TraNSIT API | 🌐 All Commodities | Optionally pick specific commodity names from L3 data |
| 📡 TraNSIT API | 🏭 By Industry Group (L2) | Select industry groups (food, livestock, mining, etc.) |
| ⚙️ User-Defined Groups | 📂 By Sector | Curated sectors: beverage, cold_food, general, health, horticulture |
| ⚙️ User-Defined Groups | 🏷️ By Industry | Curated industries: alcohol_beverage, dairy_product, fruit, meat, medicines, seafood, etc. |

**User-Defined Groups** (Dorian's custom curated commodity subsets):
```python
_SECTOR_DICT = {
    "beverage":     ["liquor", "wine"],
    "cold_food":    ["box_beef", "box_chicken", "box_lamb", "box_pigs", "cheese",
                     "chicken", "butter", "cream_yoghurt", "fish", "prawn",
                     "salmon", "barramundi", "meat", "seafood"],
    "general":      ["clothes", "footwear", "tobacco"],
    "health":       ["pbs_medicines", "medicines", "technetium_99m", "hosp_medicines"],
    "horticulture": ["almonds", "blueberries", "cherries", "macadamias", "mushrooms",
                     "nectarines", "olives", "peaches", "strawberries", "apricots"],
}

_INDUSTRY_DICT = {
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
```

### Main Content (both scopes)
- Route header, back link to Page 1
- **📥 Update / Download Local Data** collapsible expander (not needed — data already downloaded)
- Data source info note

### Charts — National Scope
- **B1** Summary Cards — OD Corridors, Total Tonnes, Median Cost/Tonne, Total CO₂, Origins with Data
- **B2** State-to-State Freight Flow Heatmap (`go.Heatmap`)
- **Top 20 National OD Corridors** — horizontal bar coloured by origin state
- **B3** Top Origins & Top Destinations — side-by-side horizontal bars (top 10 each)
- **B4** Intra-state vs Inter-state Split — donut + stacked bar per state
- **B5** Cost per Tonne Distribution by State — box plot per state
- **B7** Freight Value vs Tonnes scatter — per-state coloured dots, median crosshairs
- **R3** CO₂ vs Transport Cost scatter
- **R4** Full Rankings Table + CSV download

### Charts — Single Origin Scope
- **R1** Top 15 Destinations — horizontal bar, orange = destination selected on Page 1
- **B7** Freight Value vs Tonnes scatter — orange = selected dest, grey = others
- **R3** CO₂ vs Transport Cost scatter — orange = selected dest, grey = others
- **R4** Full Rankings Table + CSV download

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

### API Response Fields (commodityreport — Level 2)
`industry, sector, trips_count, trailer_loads, tonnes, tonne_kms, tonnes_per_trailer,
avg_trip_distance, avg_trip_duration, total_trip_distance, total_trip_duration,
total_freight_value, trip_transport_costs, cst_per_tonne, cst_per_tonne_km, co2_tn`

Level 3 adds: `commodity` field (individual name, e.g. "Beer", "Flour")

**No year/date/period field exists in any API response.**

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
# → api_local_data/<level>/<STATE>/<LGA_CODE>.json
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
    "LGA_21180": [commodity_records...],
    ...
  }
}
```

### Key Loaders
```python
# Level 2 (industry groups)
load_local_origin_data(orig_lga, orig_state)  → ({dest_lga: totals}, error)
load_all_od_pairs()                            → ([{orig_lga, orig_state, dest_lga, ...}], error)

# Level 3 (individual commodities)
load_local_origin_data_l3(orig_lga, orig_state) → ({dest_lga: totals}, error)
load_all_od_pairs_l3()                          → ([...], error)

# Level 3 with filtering (used in Page 2)
_load_all_od_pairs_l3_filtered(industry_filter: frozenset|None, commodity_filter: frozenset|None)
_load_local_origin_l3_filtered(orig_lga, orig_state, industry_filter, commodity_filter)
```

**Caching:** All API calls use `@st.cache_data(show_spinner=False)`. Local file loaders
are NOT cached (fast I/O, data may be refreshed by downloader).

---

## LGA Data (`lga_codes.py`)

- **514 Australian LGAs** across 8 states/territories
- `LGA_CODES`: `{LGA_code: display_name}`
- `LGA_NAMES`: `{display_name: LGA_code}` (reverse lookup)
- `LGA_STATE`: `{LGA_code: state_abbr}` e.g. `"LGA_24600" → "VIC"`
- `STATE_LGAS`: `{state: [sorted_LGA_names]}`
- `SORTED_NAMES`: all LGA names sorted alphabetically
- `STATE_COLORS`: `{state: hex_color}` for state badges and charts

LGA code → state: first digit after `LGA_` prefix:
`1=NSW, 2=VIC, 3=QLD, 4=SA, 5=WA, 6=TAS, 7=NT, 8=ACT`

---

## Downloader (`downloader.py`)

Background thread that downloads all commodityreport data from the API.
**Local data is already downloaded — users should NOT need this.**

2-phase process per origin:
1. `densitymap` → discover valid destination LGAs
2. `commodityreport` per valid destination → fetch commodity records

Scale: 515 LGAs, ~50,000 API calls at 0.3s each → ~2 hours for all states.

```python
# Level 3 downloader functions (used in Page 2)
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

### Plotly Layout (Page 1)
```python
_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
```
Page 2 omits `margin` from layout and sets it per-chart.

### `chart_header()` Helper (defined in both files)
```python
def chart_header(title: str, info_md: str, section: bool = True) -> None:
    """Render title + clickable ⓘ info popover in a [0.88, 0.12] column layout."""
```
- `section=True` → grey uppercase 11px section label style
- `section=False` → bold 14px chart title style
- Requires Streamlit ≥1.31 (satisfied by ≥1.35.0 requirement)

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

---

## Known Behaviours / Edge Cases

- **No year filtering:** The API has no year parameter; data represents annual totals
  for a typical representative year (varies by commodity, mostly 2021–2024).
- **Rail unavailable:** `commodityreport` is road-only. Selecting Rail shows an error.
- **All Modes = Road:** Same data returned; a warning note is shown.
- **Suppressed data:** Some OD pairs return empty list (statistical suppression for low-volume
  flows, <5 movements). App shows a graceful "No data" info message.
- **densitymap ≠ commodityreport:** Different processing pipelines — numbers differ
  significantly for the same OD pair. Page 2 Online mode shows a disclaimer.
  Use Local Data mode for numbers consistent with Page 1.
- **Rank 1 = highest value** for ALL metrics including Cost/Tonne (most expensive = Rank 1).
- **A3 Transport Cost Breakdown:** Displays total annual AUD (not cost per tonne).
- **B1 Median Cost/Tonne:** Unweighted per-corridor median, not volume-weighted.
- **Commodity filter disabled in Online mode:** Requires Local Data to apply filters.
- **Local data already downloaded:** All 8 states populated in `api_local_data/`. The
  📥 Download panel exists but users should not need it.
- **Commodity normalization:** `_normalize("Cream Yoghurt") → "cream_yoghurt"` —
  commodity names from API are title-case; local dict keys are snake_case.

---

## Quick Reference — Adding New Charts

1. Add fetch function to `api.py` using `_od_fetch(endpoint, orig, dest, mode)`
2. Add cached wrapper in `CSIRO_TraNSIT_Dashboard.py`: `@st.cache_data(show_spinner=False)`
3. Use `chart_header(title, info_md, section=False)` for chart title + ⓘ popover
4. Build: `fig = go.Figure()` → `fig.update_layout(**_PLOTLY_LAYOUT, ...)` → `st.plotly_chart(fig, use_container_width=True)`

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

No external data files required for Page 1 (live API). Page 2 requires local data
in `api_local_data/` — already downloaded, do not delete.
