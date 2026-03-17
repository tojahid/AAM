# FreightOD — TraNSIT Metrics with Visualisations

**Standalone Streamlit app** for exploring Australian road freight data from the
CSIRO TraNSIT Benchmarking platform via its public REST API (no authentication required).

---

## Folder Structure

```
apps/app_with_visualisation/
├── app.py                  ← Page 1: OD Metrics + Charts (entry point)
├── pages/
│   └── od_rankings.py      ← Page 2: OD Corridor Rankings
├── api.py                  ← All API client functions
├── lga_codes.py            ← LGA reference data (514 LGAs, names, codes, states)
├── downloader.py           ← Background download engine for local data
├── requirements.txt        ← streamlit>=1.35.0, pandas>=2.0.0, plotly>=5.0.0
├── app_details.md          ← This file
└── local_data/             ← Downloaded local data (created by downloader)
    ├── VIC/
    │   ├── LGA_24600.json  ← Melbourne origins data
    │   └── ...
    ├── NSW/
    ├── QLD/
    ├── SA/
    ├── WA/
    ├── TAS/
    ├── NT/
    └── ACT/
```

**Run command:**
```
python -m streamlit run apps/app_with_visualisation/app.py
```
Or from inside the folder:
```
streamlit run app.py
```

---

## Pages

### Page 1 — `app.py` (OD Metrics + Charts)

**Purpose:** Show all freight metrics for a selected Origin → Destination LGA pair.

**Sidebar controls:**
- Origin State (dropdown, default VIC) → Origin LGA (dropdown, default Melbourne (C))
- Destination State → Destination LGA
- Transport Mode: Road / Rail / All Modes
  - Rail: blocked (commodityreport is road-only, shows error)
  - All Modes: allowed but returns same data as Road (shows info note)
- LGA code chips shown below each selector

**Session state written (for Page 2):**
- `shared_orig_code`, `shared_orig_name`, `shared_orig_state`
- `shared_dest_code`, `shared_dest_name`
- `orig_lga_name`, `dest_lga_name` (persists selection across rerenders)

**Main content:**
1. **Route header** — `{Origin} [STATE] {LGA_CODE} → {Destination} [STATE] {LGA_CODE}`
2. **API endpoint used** (collapsible expander) — shows full URL
3. **10 Headline Metric Cards** (2 rows × 5 columns):
   - Annual Tonnes, Annual Trailers, Cost per Tonne, Total Transport Costs,
     Total Freight Value, Total Travel Distance (km), Annual Tonne-km,
     Avg Trip Distance (km), Avg Trip Duration (hrs), Total CO₂ Emissions (t)
4. **Industry Breakdown Table** — one row per industry group; TOTAL row at bottom;
   CSV downloads: Per-Industry CSV + Headline Metrics CSV
5. **Freight Profile Charts** (4 charts in 2×2 grid):
   - A1 Trip Length Distribution (grouped bar: Short/Medium/Long × sector, toggle Tonnes/Trips)
   - A2 Supply Chain Flows (horizontal bar, orig_type → dest_type sorted by tonnes)
   - A3 Transport Cost Breakdown (stacked horizontal bar by cost component: Capital/Driver/Fuel/Fixed/Maintenance/Load/Unload)
   - B4 Freight Composition by Industry (donut, hole=0.45, total tonnes in centre)
6. **Navigation link** → Page 2 (OD Corridor Rankings)
7. **Raw JSON expander** — shows full API response

---

### Page 2 — `pages/od_rankings.py` (OD Corridor Rankings)

**Purpose:** Rank freight corridors by metric. Two modes:

**Sidebar controls:**
- **Scope** (radio):
  - `🌏 All Origins — National` — loads all local data, shows top corridors nationally
  - `📍 Single Origin` — shows all destinations from one selected origin
- **Origin selector** (only in Single Origin scope): State + LGA dropdowns (independent from Page 1)
- **Filter by Origin State** multiselect (only in National scope)
- **Data Source** (only in Single Origin scope): Online API (densitymap) or Local Data
- **Rank By**: Tonnes / Cost/Tonne (AUD) / Transport Cost ($) / CO₂ (t) / Trips

**Main content:**
1. **Route header** — "National OD Corridor Rankings" OR "{Origin} → All Destinations"
2. **Back link** → Page 1
3. **📥 Update / Download Local Data** (collapsible expander):
   - Idle state: scope selector (All States or specific state), Force re-download checkbox, Start button with estimated time
   - Running: progress bar (processed/total LGAs), elapsed/ETA/pairs-saved metrics, last 8 log lines, Cancel button (auto-refreshes every 2s)
   - Done: success/warning/error message + Clear button
4. **Data note** (info box) explaining data source
5. **Charts:**
   - R1: Top 20 (national) or Top 15 (single origin) horizontal bar — highlights selected dest in orange
   - R2: Distance vs Cost/Tonne scatter — dot size ∝ tonnes, quadrant median lines
   - R3: CO₂ vs Transport Cost scatter — dot size ∝ tonnes
   - R4: Full rankings table + CSV download
6. **Rank badge** (single origin only) — shows selected destination's rank

---

## API (`api.py`)

**Base URL:** `https://benchmark.transit.csiro.au/api/benchmarking`

**Dataset:** `SIM-AU-BASELINE` (always fixed)

### Endpoints used

| Function | Endpoint | Parameters | Returns |
|---|---|---|---|
| `fetch_od_metrics()` | `commodityreport` | orig_lga, dest_lga, mode=road, groupBy_l2=true | industry records + totals |
| `fetch_trip_length()` | `triplengthreport` | orig_lga, dest_lga, mode | trip type distribution by sector |
| `fetch_supply_chain()` | `supplychainreport` | orig_lga, dest_lga, mode | supply chain node flows |
| `fetch_logistics()` | `transportlogisticsreport` | orig_lga, dest_lga, mode | cost component breakdown |
| `fetch_origin_destinations()` | `densitymap` | orig_lga, mode, regions=dest_lga | all destinations from one origin |

### Important notes
- `commodityreport` is **road-only** — Rail and All Modes return same data as Road
- `densitymap` and `commodityreport` use different processing pipelines — their numbers
  differ significantly for the same OD pair (densitymap is for discovery/comparison only)
- `groupBy_l2=true` on commodityreport → returns industry groups (not individual commodities)
- LGA code format: `LGA_XXXXX` (5-digit numeric suffix)

### Key functions

```python
# Headline metrics for one OD pair (Page 1)
records, totals, error = fetch_od_metrics(orig_lga, dest_lga, mode="road")

# Additional chart data (Page 1)
records, error = fetch_trip_length(orig_lga, dest_lga, mode)
records, error = fetch_supply_chain(orig_lga, dest_lga, mode)
records, error = fetch_logistics(orig_lga, dest_lga, mode)

# All destinations from one origin (Page 2 Single Origin, Online)
records, error = fetch_origin_destinations(orig_lga, mode="road")

# Load local data for one origin (Page 2 Single Origin, Local)
dest_dict, error = load_local_origin_data(orig_lga, orig_state)
# Returns: {dest_lga: totals_dict, ...}

# Load ALL local data for national rankings (Page 2 National)
rows, error = load_all_od_pairs()
# Returns: [{orig_lga, orig_state, dest_lga, tonnes, cost_per_tonne, ...}, ...]
```

### `_compute_totals()` fields
Aggregates raw commodity records into:
- `annual_tonnes`, `annual_trailers`, `cost_per_tonne`, `total_transport_costs`
- `total_freight_value`, `total_travel_distance_km`, `annual_tonne_km`
- `avg_trip_distance_km`, `avg_trip_duration_hrs`, `total_co2_t`
- `commodities_count`, `total_trips`

### Local data path
```python
LOCAL_DATA_ROOT = pathlib.Path(__file__).parent / "local_data"
# → apps/app_with_visualisation/local_data/<STATE>/<LGA_CODE>.json
```

### Local data file format
```json
{
  "orig_lga": "LGA_24600",
  "orig_name": "Melbourne (C)",
  "orig_state": "VIC",
  "fetched_at": "2025-03-12T10:00:00+00:00",
  "destinations": {
    "LGA_24600": [commodity_records...],
    "LGA_24650": [commodity_records...],
    ...
  }
}
```

---

## LGA Data (`lga_codes.py`)

- **514 Australian LGAs** across 8 states/territories
- `LGA_CODES`: `{LGA_code: display_name}`
- `LGA_NAMES`: `{display_name: LGA_code}` (reverse lookup)
- `LGA_STATE`: `{LGA_code: state_abbreviation}` e.g. `"LGA_24600" → "VIC"`
- `STATE_LGAS`: `{state: [sorted_LGA_names]}` e.g. `"VIC" → ["Alpine (S)", ...]`
- `SORTED_NAMES`: all LGA names sorted alphabetically
- `STATE_COLORS`: `{state: hex_color}` for badge rendering

State abbreviations: `NSW`, `VIC`, `QLD`, `SA`, `WA`, `TAS`, `NT`, `ACT`

LGA code → state mapping: first digit after `LGA_` prefix:
`1=NSW, 2=VIC, 3=QLD, 4=SA, 5=WA, 6=TAS, 7=NT, 8=ACT`

---

## Downloader (`downloader.py`)

Background thread that downloads all commodityreport data from the API and saves
to `local_data/`. Same logic as the external `fetch_all_data.py` script.

**2-phase process per origin LGA:**
1. `densitymap` call → discover which destination LGAs have data (avoids 265k blind calls)
2. `commodityreport` call per valid destination → fetch detailed commodity records

**Scale:** 515 LGAs, ~50,000 total API calls at 0.3s each → ~2 hours for all states.
**Rate limit:** 0.3s between calls, 3 retries with 2s backoff.
**Resume support:** existing files are skipped (force=False by default).

### Public API
```python
from downloader import start_download, cancel_download, get_progress

start_download(state_filter="VIC", force=False)  # start background thread
cancel_download()                                  # signal stop after current LGA
prog = get_progress()                              # DownloadProgress singleton
```

### `DownloadProgress` attributes
```python
prog.running        # bool — download in progress
prog.done           # bool — completed (success, cancel, or error)
prog.cancelled      # bool — user requested cancel
prog.error          # str | None — exception message if failed
prog.total_lgas     # int — total LGAs to process
prog.processed      # int — LGAs completed (includes skipped)
prog.skipped        # int — LGAs skipped (already cached)
prog.total_pairs    # int — OD pairs with data saved
prog.current_code   # str — LGA code currently being processed
prog.current_name   # str — LGA name currently being processed
prog.current_state  # str — state of current LGA
prog.start_time     # float — time.time() at start
prog.log_lines      # list[str] — last 25 completed LGA log entries
```

---

## Design System

### Colours
| Variable | Hex | Use |
|---|---|---|
| `_BLUE` | `#2563EB` | Default bars, primary metric card border |
| `_ORANGE` | `#F97316` | Selected/highlighted destination, fuel cost |
| `_GREEN` | `#10B981` | Cost/efficiency, load cost |
| `_RED` | `#DC2626` | CO₂, high-cost |
| `_PURPLE` | `#7C3AED` | Distance, maintenance cost |
| `_AMBER` | `#D97706` | Freight value, unload cost |
| `_TEAL` | `#0D9488` | Fixed cost, transport cost |
| `_INDIGO` | `#4F46E5` | Trailers, driver cost |

Sidebar background: `#1E3A5F` (dark navy)
Sidebar text: `#C8DAF0` (light blue-white)
Section labels: `#9CA3AF` (grey, uppercase, 11px)

### Plotly layout
```python
_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
```
All charts use `st.plotly_chart(fig, use_container_width=True)`.

### Caching
All API calls wrapped with `@st.cache_data(show_spinner=False)`.
`load_local_origin_data()` and `load_all_od_pairs()` are NOT cached
(fast file I/O, data may be updated by downloader).

---

## Session State Keys

| Key | Set by | Used by | Purpose |
|---|---|---|---|
| `shared_orig_code` | app.py sidebar | od_rankings.py | Pass origin to Page 2 |
| `shared_orig_name` | app.py sidebar | od_rankings.py | Pass origin name |
| `shared_orig_state` | app.py sidebar | od_rankings.py | Pass state abbreviation |
| `shared_dest_code` | app.py sidebar | od_rankings.py | Highlight dest in Page 2 |
| `shared_dest_name` | app.py sidebar | od_rankings.py | Highlight dest name |
| `orig_lga_name` | app.py sidebar | app.py | Persist origin selection across rerenders |
| `dest_lga_name` | app.py sidebar | app.py | Persist dest selection across rerenders |
| `rank_orig_state` | od_rankings.py sidebar | od_rankings.py | Origin state on Page 2 |
| `rank_orig_lga_name` | od_rankings.py sidebar | od_rankings.py | Origin LGA on Page 2 |

---

## Known Behaviours / Edge Cases

- **Local trips:** `local_trips=true` — includes same-LGA (origin = destination) flows;
  for local trips, `avg_trip_distance` and `avg_trip_duration` are set to 0 in `_compute_totals`
- **Suppressed data:** Some OD pairs return empty list from API (statistical suppression
  for low-volume flows). App shows a graceful "No data" info message.
- **Rail data:** Not available via `commodityreport`. Selecting Rail shows an error and stops rendering.
- **densitymap vs commodityreport mismatch:** Numbers differ by a large factor between
  the two endpoints for the same OD pair. Page 2 (Online mode) shows a disclaimer note.
- **National rankings** require local data. If `local_data/` is empty, users see
  a warning with instructions to use the download button.
- **Download thread persistence:** The `_progress` singleton in `downloader.py` is
  module-level, surviving Streamlit reruns but NOT server restarts.

---

## Dependencies

```
streamlit>=1.35.0
pandas>=2.0.0
plotly>=5.0.0
```

No external data files required to run Page 1. Page 2 national rankings require
downloading local data via the in-app download button.

---

## Quick Reference — Adding New Charts

1. Add a fetch function to `api.py` using `_od_fetch(endpoint, orig, dest, mode)`
2. Add a cached wrapper in `app.py`: `@st.cache_data(show_spinner=False)`
3. Call the cached wrapper in the Section 3 chart grid
4. Use `go.Figure()` + `fig.update_layout(**_PLOTLY_LAYOUT, ...)` + `st.plotly_chart(fig, use_container_width=True)`
