# MEMORY.md — localis_sampledata_passenger_cloud_app

## Purpose
Cloud-ready copy of `localis_sampledata_passenger_app` for deployment on Streamlit Cloud.
This folder IS the GitHub repo root — data files go in `output/`.

## Key differences from local app
- Paths: pages use `Path(__file__).parent.parent / "output"` (2 hops, not 3)
- Export paths: use `Path(tempfile.gettempdir())` — Streamlit Cloud repo dir is read-only
- Added: `requirements.txt`, `.streamlit/config.toml`

## Data files (output/)
| File | Size | Git action |
|------|------|------------|
| ranked_corridors.csv | small | commit normally |
| temporal_distribution_all.csv | ~15 MB | commit normally |
| trips_20GB.csv | ~755 MB | Git LFS required |
| trips.parquet | optional | Git LFS if included |

## Deployment
1. Push this folder as a GitHub repository
2. Streamlit Cloud → New app → set Main file path: `app.py`
3. Deploy

## Run locally
```
streamlit run localis_sampledata_passenger_cloud_app/app.py
```
(run from `vic_trip_topn_localis_sample_app/`)
