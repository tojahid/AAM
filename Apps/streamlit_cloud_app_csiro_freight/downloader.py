"""
downloader.py — Background API data downloader for OD Rankings page.

Replicates fetch_all_data.py logic (2-phase: densitymap discovery + commodityreport fetch)
but designed to run as a background thread from within the Streamlit app.

Phase 1 — Discovery:
    For each origin LGA, call densitymap to discover which destination LGAs have data.

Phase 2 — Fetch:
    For each valid (origin, destination) pair, call commodityreport for detailed records.

Saves to:
    apps/app_with_visualisation/local_data/<STATE>/<LGA_CODE>.json

Same file format as the existing local data (compatible with api.load_local_origin_data
and api.load_all_od_pairs).
"""

import json
import pathlib
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from lga_codes import LGA_CODES, LGA_STATE

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

LOCAL_DATA_ROOT    = pathlib.Path(__file__).parent / "api_local_data" / "level2"
LOCAL_DATA_ROOT_L3 = pathlib.Path(__file__).parent / "api_local_data" / "level3"

# ---------------------------------------------------------------------------
# API constants (same parameters as fetch_all_data.py)
# ---------------------------------------------------------------------------

_DENSITYMAP_URL = "https://benchmark.transit.csiro.au/api/benchmarking/densitymap"
_COMMODITY_URL  = "https://benchmark.transit.csiro.au/api/benchmarking/commodityreport"

CALL_DELAY_S  = 0.3   # seconds between every API call
MAX_RETRIES   = 3     # retry attempts before skipping a pair
RETRY_DELAY_S = 2.0   # seconds between retries on error

# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

class DownloadProgress:
    """Thread-safe progress tracking for the background download."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.running        = False
            self.done           = False
            self.cancelled      = False
            self.error: str | None = None
            self.total_lgas     = 0
            self.processed      = 0   # includes skipped
            self.skipped        = 0
            self.total_pairs    = 0
            self.current_code   = ""
            self.current_name   = ""
            self.current_state  = ""
            self.start_time: float | None = None
            self.log_lines: list[str] = []


# Module-level singleton — shared between Streamlit reruns via the module cache
_progress = DownloadProgress()


def get_progress() -> DownloadProgress:
    """Return the global DownloadProgress instance."""
    return _progress


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get_json(url: str) -> list | None:
    """Fetch URL and return parsed JSON. Returns None on persistent failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                return json.load(resp)
        except (urllib.error.URLError, urllib.error.HTTPError):
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Phase 1 — discover destinations for one origin
# ---------------------------------------------------------------------------

def _discover_destinations(orig_lga: str) -> list[str]:
    """Return dest_lga codes reachable from orig_lga via densitymap."""
    params = urllib.parse.urlencode({
        "dataset":              "SIM-AU-BASELINE",
        "metric":               "cst_per_tonne",
        "regions":              "dest_lga",
        "value_type":           "total",
        "local_trips":          "true",
        "orig_region_category": "orig_lga",
        "mode":                 "road",
        "orig_region":          orig_lga,
    })
    data = _get_json(f"{_DENSITYMAP_URL}?{params}")
    time.sleep(CALL_DELAY_S)
    if not isinstance(data, list):
        return []
    return [r["dest_lga"] for r in data if r.get("dest_lga")]


# ---------------------------------------------------------------------------
# Phase 2 — fetch commodityreport for one OD pair
# ---------------------------------------------------------------------------

def _fetch_commodity(orig_lga: str, dest_lga: str) -> list:
    """Return raw commodity records for one OD pair (empty list if suppressed)."""
    params = urllib.parse.urlencode({
        "dataset":              "SIM-AU-BASELINE",
        "metric":               "cst_per_tonne",
        "value_type":           "total",
        "local_trips":          "true",
        "regions":              "orig_lga",
        "orig_region_category": "orig_lga",
        "dest_region_category": "dest_lga",
        "groupBy_l2":           "true",
        "mode":                 "road",
        "orig_region":          orig_lga,
        "dest_region":          dest_lga,
    })
    data = _get_json(f"{_COMMODITY_URL}?{params}")
    time.sleep(CALL_DELAY_S)
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Phase 2 (Level 3) — fetch individual commodity records for one OD pair
# ---------------------------------------------------------------------------

def _fetch_commodity_l3(orig_lga: str, dest_lga: str) -> list:
    """Return Level 3 commodity records (groupBy_l2=false) for one OD pair."""
    params = urllib.parse.urlencode({
        "dataset":              "SIM-AU-BASELINE",
        "metric":               "cst_per_tonne",
        "value_type":           "total",
        "local_trips":          "true",
        "regions":              "orig_lga",
        "orig_region_category": "orig_lga",
        "dest_region_category": "dest_lga",
        "groupBy_l2":           "false",
        "mode":                 "road",
        "orig_region":          orig_lga,
        "dest_region":          dest_lga,
    })
    data = _get_json(f"{_COMMODITY_URL}?{params}")
    time.sleep(CALL_DELAY_S)
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Save one origin file
# ---------------------------------------------------------------------------

def _save_origin(orig_lga: str, orig_state: str, destinations: dict) -> None:
    """Write local_data/<STATE>/<LGA_CODE>.json."""
    state_dir = LOCAL_DATA_ROOT / orig_state
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "orig_lga":    orig_lga,
        "orig_name":   LGA_CODES.get(orig_lga, orig_lga),
        "orig_state":  orig_state,
        "fetched_at":  datetime.now(timezone.utc).isoformat(),
        "destinations": destinations,
    }
    out_path = state_dir / f"{orig_lga}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Background download thread
# ---------------------------------------------------------------------------

def _run_download(state_filter: str | None, force: bool) -> None:
    p = _progress
    p.running    = True
    p.done       = False
    p.cancelled  = False
    p.error      = None
    p.start_time = time.time()
    p.log_lines  = []

    targets = [
        (code, name)
        for code, name in LGA_CODES.items()
        if state_filter is None or LGA_STATE.get(code) == state_filter
    ]
    p.total_lgas  = len(targets)
    p.processed   = 0
    p.skipped     = 0
    p.total_pairs = 0

    try:
        for code, name in targets:
            if p.cancelled:
                break

            state    = LGA_STATE.get(code, "Other")
            out_path = LOCAL_DATA_ROOT / state / f"{code}.json"

            p.current_code  = code
            p.current_name  = name
            p.current_state = state

            # Skip if already cached and force is not set
            if not force and out_path.exists():
                p.skipped  += 1
                p.processed += 1
                continue

            # Phase 1: discover destinations
            dest_codes = _discover_destinations(code)

            # Phase 2: fetch commodity data
            destinations: dict[str, list] = {}
            for dest_lga in dest_codes:
                if p.cancelled:
                    break
                destinations[dest_lga] = _fetch_commodity(code, dest_lga)

            pairs = sum(1 for r in destinations.values() if r)
            p.total_pairs += pairs
            _save_origin(code, state, destinations)
            p.processed += 1

            msg = f"[{state}] {code}  {name}: {pairs} pairs"
            p.log_lines.append(msg)
            if len(p.log_lines) > 25:
                p.log_lines = p.log_lines[-25:]

    except Exception as exc:
        p.error = str(exc)
    finally:
        p.running = False
        p.done    = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_download(state_filter: str | None = None, force: bool = False) -> bool:
    """
    Start the background download. Returns False if already running.

    Args:
        state_filter: two-letter state abbreviation (e.g. 'VIC') or None for all.
        force: if True, re-download even if the file already exists.
    """
    if _progress.running:
        return False
    _progress.reset()
    t = threading.Thread(
        target=_run_download,
        args=(state_filter, force),
        daemon=True,
    )
    t.start()
    return True


def cancel_download() -> None:
    """Signal the running download to stop after the current LGA."""
    _progress.cancelled = True


# ---------------------------------------------------------------------------
# Level 3 download — saves to api_local_data/level3/
# ---------------------------------------------------------------------------

_progress_l3 = DownloadProgress()


def get_progress_l3() -> DownloadProgress:
    """Return the global Level 3 DownloadProgress instance."""
    return _progress_l3


def _run_download_l3(state_filter: str | None, force: bool) -> None:
    p = _progress_l3
    p.running    = True
    p.done       = False
    p.cancelled  = False
    p.error      = None
    p.start_time = time.time()
    p.log_lines  = []

    targets = [
        (code, name)
        for code, name in LGA_CODES.items()
        if state_filter is None or LGA_STATE.get(code) == state_filter
    ]
    p.total_lgas  = len(targets)
    p.processed   = 0
    p.skipped     = 0
    p.total_pairs = 0

    try:
        for code, name in targets:
            if p.cancelled:
                break

            state    = LGA_STATE.get(code, "Other")
            out_path = LOCAL_DATA_ROOT_L3 / state / f"{code}.json"

            p.current_code  = code
            p.current_name  = name
            p.current_state = state

            if not force and out_path.exists():
                p.skipped   += 1
                p.processed += 1
                continue

            # Phase 1: discover destinations (same as Level 2)
            dest_codes = _discover_destinations(code)

            # Phase 2: fetch Level 3 commodity data
            destinations: dict[str, list] = {}
            for dest_lga in dest_codes:
                if p.cancelled:
                    break
                destinations[dest_lga] = _fetch_commodity_l3(code, dest_lga)

            pairs = sum(1 for r in destinations.values() if r)
            p.total_pairs += pairs

            # Save to level3 directory
            state_dir = LOCAL_DATA_ROOT_L3 / state
            state_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "orig_lga":    code,
                "orig_name":   LGA_CODES.get(code, code),
                "orig_state":  state,
                "fetched_at":  __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
                "destinations": destinations,
            }
            out_path_w = state_dir / f"{code}.json"
            with open(out_path_w, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)

            p.processed += 1
            msg = f"[{state}] {code}  {name}: {pairs} pairs (L3)"
            p.log_lines.append(msg)
            if len(p.log_lines) > 25:
                p.log_lines = p.log_lines[-25:]

    except Exception as exc:
        p.error = str(exc)
    finally:
        p.running = False
        p.done    = True


def start_download_l3(state_filter: str | None = None, force: bool = False) -> bool:
    """
    Start the Level 3 background download. Returns False if already running.

    Args:
        state_filter: two-letter state abbreviation (e.g. 'VIC') or None for all.
        force: if True, re-download even if the file already exists.
    """
    if _progress_l3.running:
        return False
    _progress_l3.reset()
    t = threading.Thread(
        target=_run_download_l3,
        args=(state_filter, force),
        daemon=True,
    )
    t.start()
    return True


def cancel_download_l3() -> None:
    """Signal the Level 3 running download to stop after the current LGA."""
    _progress_l3.cancelled = True
