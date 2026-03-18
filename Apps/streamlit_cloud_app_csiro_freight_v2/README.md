# CSIRO TraNSIT Freight OD Explorer V2
> This version has two phase of figure
- Commodity Filter Insights
- National Summary



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

