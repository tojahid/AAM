# CSIRO TraNSIT Freight OD Explorer

A standalone **2-page Streamlit app** for exploring Australian road freight data from the
[CSIRO TraNSIT Benchmarking platform](https://benchmark.transit.csiro.au) via its public
REST API. Built for freight analysts to understand what moves, where, at what cost, and
how much CO₂ is emitted — down to individual commodity level.

---

## Quick Start

```bash
# From repo root:
python -m streamlit run streamlit_cloud_app_csiro_freight_v2/CSIRO_TraNSIT_Dashboard.py

# Or from inside this folder:
streamlit run CSIRO_TraNSIT_Dashboard.py
```

**Dependencies:**
```
streamlit>=1.35.0
pandas>=2.0.0
plotly>=5.0.0
```

---

## What It Does

| Page | Purpose |
|---|---|
| **Page 1** — CSIRO TraNSIT Dashboard | Enter an Origin → Destination LGA pair; view 10 headline metrics, industry breakdown table, and 4 freight profile charts |
| **Page 2** — Commodity OD Rankings | Rank all freight corridors nationally or from a single origin; filter by commodity/industry; explore dynamic charts driven by a "Rank By" selector |

---

## Folder Structure

```
streamlit_cloud_app_csiro_freight_v2/
├── CSIRO_TraNSIT_Dashboard.py     ← Page 1: OD Metrics + Charts
├── pages/
│   └── Commodity_OD_Rankings.py  ← Page 2: Commodity Rankings
├── api.py                         ← All API client + local data loaders
├── lga_codes.py                   ← 514 Australian LGAs (names, codes, states)
├── downloader.py                  ← Background download engine (not needed — data pre-loaded)
├── requirements.txt
├── CLAUDE.md                      ← Developer reference (architecture, patterns, edge cases)
├── README.md                      ← This file
└── api_local_data/                ← Pre-downloaded local data (already populated)
    ├── level2/                    ← Industry-group data (groupBy_l2=true)
    │   └── <STATE>/LGA_XXXXX.json
    └── level3/                    ← Individual commodity data (groupBy_l2=false)
        └── <STATE>/LGA_XXXXX.json
```

> **Note:** `api_local_data/` is pre-populated for all 8 states. Users do **not** need to
> use the in-app download panel.

---

## About the Data

### Source
CSIRO TraNSIT Benchmarking platform — public REST API, no authentication required.
**Dataset:** `SIM-AU-BASELINE` (fixed — cannot be changed).

### Is it annual?
Yes. All metrics (tonnes, costs, CO₂, trailers, etc.) represent **annual volumes and values**
for one typical production year per the official CSIRO documentation.

### Which year?
There is **no single fixed year** — CSIRO uses the most recent available data per commodity:

| Commodity | Data year |
|---|---|
| Cattle & Sheep | 2022–2023 |
| Cotton | 2024 harvest |
| General Freight & Beverages | 2021–2023 |
| Processed Food (beef, chicken, lamb) | 2023 |
| Mining | 2014/2015 base, updated 2024 |
| Grain | 2018 locations + 2024 silo volumes |
| Vehicles | 2023 |
| Fuel | 2022 |
| Household Waste | 2018 |
| Forestry | 25-year rotation average |

### Can I filter by year?
**No.** The API has no year parameter (silently ignored). No year field exists in any
API response. Year-on-year comparison is not supported by the platform.

---

## Page 1 — CSIRO TraNSIT Dashboard

### Sidebar Controls
- **Origin State** dropdown (default: VIC) → **Origin LGA** (default: Melbourne (C))
- **Destination State** → **Destination LGA**
- **Transport Mode:** Road / Rail / All Modes
  - Rail: blocked — `commodityreport` is road-only, shows error
  - All Modes: returns same data as Road (shows warning)
- LGA code chip shown below each selector

### Main Content

1. **Route Header** — `{Origin} [STATE] LGA_CODE → {Dest} [STATE] LGA_CODE`
2. **API Endpoint Expander** — shows full URL used for the request
3. **10 Headline Metric Cards** (2 rows × 5 columns):

| Card | Value |
|---|---|
| Annual Tonnes | SUM(tonnes) |
| Annual Trailers | SUM(trailer_loads) |
| Cost per Tonne | SUM(costs) / SUM(tonnes) |
| Total Transport Costs | SUM(trip_transport_costs) |
| Total Freight Value | SUM(total_freight_value) |
| Total Travel Distance (km) | SUM(total_trip_distance) |
| Annual Tonne-km | SUM(tonne_kms) |
| Avg Trip Distance (km) | Trip-weighted average |
| Avg Trip Duration (hrs) | Trip-weighted average |
| Total CO₂ (t) | SUM(co2_tn) |

4. **Industry Breakdown Table** — per Level 2 industry group; TOTAL row at bottom;
   columns: Industry, Sector, Trips, Tonnes, Trailers, Transport Cost ($), Freight Value ($),
   Cost/t ($), Tonne-km, Total Distance (km), CO₂ (t); CSV download buttons

5. **4 Freight Profile Charts** (2×2 grid, each with ⓘ info popover):
   - **A1** Trip Length Distribution — grouped bar: Short/Medium/Long × sector; toggle Tonnes/Trips
   - **A2** Supply Chain Flows — horizontal bar, orig_type → dest_type sorted by tonnes
   - **A3** Transport Cost Breakdown — stacked horizontal bar by cost component
     (Capital / Driver / Fuel / Fixed / Maintenance / Load / Unload); **total annual AUD**, not per-tonne
   - **B4** Freight Composition by Industry — donut chart, hole=0.45, total tonnes in centre

6. **Navigation link** → Page 2 (Commodity OD Rankings)
7. **Raw JSON expander** — full API response

---

## Page 2 — Commodity OD Rankings

### Sidebar Controls

| Control | Description |
|---|---|
| **Scope** | 🌏 All Origins — National / 📍 Single Origin |
| **Origin selector** | State + LGA dropdowns (Single Origin only; independent from Page 1) |
| **Filter by Origin State** | Multiselect (National scope only) |
| **Data Source** | 📶 Online (API) / 💾 Local Data (Single Origin only) |
| **Rank By** | Tonnes / Cost/Tonne (AUD) / Transport Cost ($) / CO₂ (t) / Trips |
| **Commodity Filter** | All Commodities / By Industry Group / By Sector / By Industry (Local Data only) |

> **Rank 1 = highest value** for ALL metrics. For Cost/Tonne, Rank 1 is the most expensive corridor.

### Commodity Filter Options

| Category | Filter Type | Selects |
|---|---|---|
| 📡 TraNSIT API | 🌐 All Commodities | Specific commodity names from L3 data |
| 📡 TraNSIT API | 🏭 By Industry Group (L2) | Industry groups (food, livestock, mining, etc.) |
| ⚙️ User-Defined Groups | 📂 By Sector | Curated sets: beverage, cold_food, general, health, horticulture |
| ⚙️ User-Defined Groups | 🏷️ By Industry | Curated sets: meat, seafood, dairy_product, medicines, etc. |

### Charts — National Scope

| Chart | Type | Dynamic? | Description |
|---|---|---|---|
| **B1** Summary Cards | `st.metric` | Partial | 5 cards — OD Corridors, Total Tonnes, **Median [rank_metric]**, Total CO₂, Origins with Data |
| **B2** State-to-State Heatmap | `go.Heatmap` | Fixed | Tonne flows between state pairs |
| **R1** Top 20 National OD Corridors | `go.Bar` H | ✅ Yes | x-axis = rank_field; coloured by origin state |
| **B3** Top Origins & Destinations | `go.Bar` H | ✅ Yes | Top 10 each; x-axis = rank_field; title includes rank metric |
| **B4** Intra vs Inter-state Split | `go.Pie` + `go.Bar` | Fixed | Tonnage split; donut + stacked bar per state |
| **B5** Cost/Tonne Distribution | `go.Box` | Fixed | Box plot per state, always cost/tonne |
| **B7** Freight Value vs Tonnes | `go.Scatter` | Fixed | Per-state coloured dots, median crosshairs |
| **R3** CO₂ vs Transport Cost | `go.Scatter` | Fixed | Grey dots, dot size ∝ tonnes |
| **R4** Full Rankings Table | `st.dataframe` | ✅ Yes | Sorted by rank_field; CSV download |

### Charts — Single Origin Scope

| Chart | Type | Dynamic? | Description |
|---|---|---|---|
| **R1** Top 15 Destinations | `go.Bar` H | ✅ Yes | x-axis = rank_field; orange = Page 1 selection |
| **B7** Freight Value vs Tonnes | `go.Scatter` | Fixed | Orange = selected dest, grey = others |
| **R3** CO₂ vs Transport Cost | `go.Scatter` | Fixed | Orange = selected dest, grey = others |
| **R4** Full Rankings Table | `st.dataframe` | ✅ Yes | Sorted by rank_field; CSV download |

### Commodity Filter Insights Section

Appears **only** when a Commodity Filter is active AND data source is Local Data.

```
🔬 COMMODITY FILTER INSIGHTS  [ⓘ]
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Commodities  │ Total Tonnes │ Avg Cost/t   │ Total CO₂    │
└──────────────┴──────────────┴──────────────┴──────────────┘
  Chart A: Commodity Share by {rank_metric}  │  Chart B: Cost vs Volume (fixed)
───────────────────────────────────────────────────────────
  Chart 1: Multi-Metric Comparison Table         (full width)
  Chart 2: Freight Value-to-Cost Ratio bar       (full width)
  Chart 3: Top 10 OD Corridors by Commodity      (full width, tabbed)
───────────────────────────────────────────────────────────
```

| Component | Dynamic? | Notes |
|---|---|---|
| 4 Metric Cards | Fixed | Always: Commodities, Tonnes, Avg Cost/t, CO₂ |
| **Chart A** Commodity Share | ✅ Rank By | Title, x-axis, hover use `rank_field` |
| **Chart B** Cost vs Volume | Fixed | Always X=tonnes, Y=cost/tonne; dot size ∝ CO₂ |
| **Chart 1** Comparison Table | Partially | Row order follows `rank_field` sort |
| **Chart 2** Value-to-Cost Ratio | Fixed | Always shows freight_value / transport_cost |
| **Chart 3** Top OD Corridors | ✅ Rank By | Bar order follows `rank_field`; tab order follows commodity rank |

> **Known limitation — Chart 3:** Corridors are pre-loaded as top-10 by tonnes. When a
> different rank is selected, bars re-order within those 10 — routes ranked higher by
> Trips or CO₂ but outside the tonnes top-10 will not appear.

---

## LGA Coverage

- **514 Australian LGAs** across 8 states/territories
- State → LGA code prefix: `1=NSW, 2=VIC, 3=QLD, 4=SA, 5=WA, 6=TAS, 7=NT, 8=ACT`
- LGA code format: `LGA_XXXXX` (5-digit numeric suffix)

---

## Key Known Limitations

- **No year filtering** — API silently ignores any year parameter; data represents annual totals (~2021–2024 depending on commodity)
- **Road freight only** — Rail is not available via `commodityreport`; selecting Rail shows an error
- **All Modes = Road** — Same data returned; a warning note is shown
- **Suppressed data** — OD pairs with fewer than ~5 movements are suppressed by CSIRO and return an empty list; app shows a graceful "No data" info message
- **Online ≠ Local Data numbers** — `densitymap` (Online) and `commodityreport` (Local Data) use different processing pipelines; numbers differ for the same OD pair; use Local Data for consistency with Page 1
- **Rank 1 = highest value** — for Cost/Tonne, the most expensive corridor ranks #1
- **B1 Median card may show $0.00 or 0** — when a commodity filter is active and CSIRO data suppression leaves most corridors with zero values for those commodities; correct but potentially misleading; info popover explains
- **Commodity Filter Insights unavailable in Online mode** — requires Local Data
- **Chart 3 top-10 pre-selection** — see note above under Commodity Filter Insights

---

## Design System

### Colour Tokens

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

Sidebar: background `#1E3A5F` · text `#C8DAF0` · dividers `#2E5A8C`

### State Colours (from `lga_codes.py` → `STATE_COLORS`)

Used for bar colours in B3, R1, Chart 3, and state badge chips.

### Plotly Layout Base

```python
_PLOTLY_LAYOUT = dict(
    template="plotly_white",
    font=dict(family="Inter, system-ui, sans-serif", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)
```

> Page 2 omits `margin` from `_PLOTLY_LAYOUT` and sets it per-chart.

---

## API Reference

**Base URL:** `https://benchmark.transit.csiro.au/api/benchmarking`

| Endpoint | Function | Key Params |
|---|---|---|
| `commodityreport` | `fetch_od_metrics()` | orig_lga, dest_lga, mode=road, groupBy_l2=true |
| `triplengthreport` | `fetch_trip_length()` | orig_lga, dest_lga, mode |
| `supplychainreport` | `fetch_supply_chain()` | orig_lga, dest_lga, mode |
| `transportlogisticsreport` | `fetch_logistics()` | orig_lga, dest_lga, mode |
| `densitymap` | `fetch_origin_destinations()` | orig_lga, mode |

### Local Data Paths

```python
api_local_data/level2/<STATE>/LGA_XXXXX.json   # Industry-group data
api_local_data/level3/<STATE>/LGA_XXXXX.json   # Individual commodity data
```

### Local Data File Format

```json
{
  "orig_lga": "LGA_24600",
  "orig_name": "Melbourne (C)",
  "orig_state": "VIC",
  "fetched_at": "2026-03-12T06:45:59+00:00",
  "destinations": {
    "LGA_24600": [ ...commodity_records ],
    "LGA_21180": [ ...commodity_records ]
  }
}
```

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
