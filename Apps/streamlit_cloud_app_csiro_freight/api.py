"""
api.py  —  API clients for the FreightOD visualisation app

Includes:
  - commodityreport: OD headline metrics (existing, unchanged)
  - triplengthreport: trip length distribution
  - supplychainreport: supply chain node flows
  - transportlogisticsreport: cost component breakdown
  - densitymap (dest mode): all destinations from an origin (for rankings)
  - load_local_origin_data: read pre-downloaded offline JSON for rankings
"""

import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Existing: commodityreport — OD headline metrics
# ---------------------------------------------------------------------------

BASE_URL = "https://benchmark.transit.csiro.au/api/benchmarking/commodityreport"

_FIXED_PARAMS = {
    "dataset":              "SIM-AU-BASELINE",
    "metric":               "cst_per_tonne",
    "value_type":           "total",
    "local_trips":          "true",
    "regions":              "orig_lga",
    "orig_region_category": "orig_lga",
    "dest_region_category": "dest_lga",
    "groupBy_l2":           "true",
}


def build_url(orig_lga: str, dest_lga: str, mode: str | None = "road") -> str:
    """Return the full commodityreport URL for an OD pair."""
    p = {**_FIXED_PARAMS, "orig_region": orig_lga, "dest_region": dest_lga}
    if mode:
        p["mode"] = mode
    return f"{BASE_URL}?{urllib.parse.urlencode(p)}"


def _compute_totals(records: list[dict], is_local: bool = False) -> dict:
    """Aggregate per-commodity/industry records into headline metric totals."""
    def s(field):
        return sum(r.get(field, 0) for r in records)

    total_tonnes = s("tonnes")
    total_trips  = s("trips_count")
    total_cost   = s("trip_transport_costs")

    if is_local or total_trips == 0:
        avg_dist = 0.0
        avg_dur  = 0.0
    else:
        avg_dist = sum(r.get("avg_trip_distance", 0) * r.get("trips_count", 0) for r in records) / total_trips
        avg_dur  = sum(r.get("avg_trip_duration", 0) * r.get("trips_count", 0) for r in records) / total_trips

    return {
        "annual_tonnes":             total_tonnes,
        "annual_trailers":           s("trailer_loads"),
        "cost_per_tonne":            total_cost / total_tonnes if total_tonnes else 0,
        "total_transport_costs":     total_cost,
        "total_freight_value":       s("total_freight_value"),
        "total_travel_distance_km":  s("total_trip_distance"),
        "annual_tonne_km":           s("tonne_kms"),
        "avg_trip_distance_km":      avg_dist,
        "avg_trip_duration_hrs":     avg_dur,
        "total_co2_t":               s("co2_tn"),
        "commodities_count":         len(records),
        "total_trips":               total_trips,
    }


def fetch_od_metrics(
    orig_lga: str,
    dest_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], dict | None, str | None]:
    """
    Fetch commodityreport records for an Origin → Destination LGA pair.

    Returns:
        (records, headline_totals, error)
    """
    url = build_url(orig_lga, dest_lga, mode)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = json.load(resp)
    except urllib.error.URLError as exc:
        return [], None, f"Network error: {exc.reason}"
    except json.JSONDecodeError:
        return [], None, "API returned invalid JSON."

    if not isinstance(raw, list):
        return [], None, f"Unexpected response type: {type(raw).__name__}"

    if not raw:
        return [], None, None

    return raw, _compute_totals(raw, is_local=(orig_lga == dest_lga)), None


# ---------------------------------------------------------------------------
# New: shared constants for additional OD endpoints
# ---------------------------------------------------------------------------

_BASE = "https://benchmark.transit.csiro.au/api/benchmarking"

_OD_FIXED = {
    "dataset":              "SIM-AU-BASELINE",
    "metric":               "cst_per_tonne",
    "value_type":           "total",
    "local_trips":          "true",
    "regions":              "orig_lga",
    "orig_region_category": "orig_lga",
    "dest_region_category": "dest_lga",
    "groupBy_l2":           "false",
}


def _od_fetch(
    endpoint: str,
    orig_lga: str,
    dest_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], str | None]:
    """Generic OD fetch helper for extra report endpoints."""
    p = {**_OD_FIXED, "orig_region": orig_lga, "dest_region": dest_lga}
    if mode:
        p["mode"] = mode
    url = f"{_BASE}/{endpoint}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = json.load(resp)
        return (raw if isinstance(raw, list) else []), None
    except urllib.error.URLError as exc:
        return [], f"Network error: {exc.reason}"
    except json.JSONDecodeError:
        return [], "API returned invalid JSON."


# ---------------------------------------------------------------------------
# New: triplengthreport — trip length distribution
# ---------------------------------------------------------------------------

def fetch_trip_length(
    orig_lga: str,
    dest_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], str | None]:
    """
    Fetch trip length report for an OD pair.

    Returns records with fields:
        commod_l3, trip_type (Short/Medium/Long), trips, tonnes,
        trailer_loads, avg_trip_distance, cst_per_tonne, co2_tn,
        trip_transport_costs, total_freight_value
    """
    return _od_fetch("triplengthreport", orig_lga, dest_lga, mode)


# ---------------------------------------------------------------------------
# New: supplychainreport — supply chain node flows
# ---------------------------------------------------------------------------

def fetch_supply_chain(
    orig_lga: str,
    dest_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], str | None]:
    """
    Fetch supply chain report for an OD pair.

    Returns records with fields:
        orig_type, dest_type, orig_category, dest_category,
        trips, tonnes, trailer_loads, avg_trip_distance,
        trip_transport_costs, total_freight_value, cst_per_tonne, co2_tn
    """
    return _od_fetch("supplychainreport", orig_lga, dest_lga, mode)


# ---------------------------------------------------------------------------
# New: transportlogisticsreport — cost component breakdown
# ---------------------------------------------------------------------------

def fetch_logistics(
    orig_lga: str,
    dest_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], str | None]:
    """
    Fetch transport logistics cost breakdown for an OD pair.

    Returns records with fields:
        commod_l3, capital_cost, driver_cost, fuel_cost, fixed_cost,
        maintenance_cost, load_c, unload_c, logistic_cost,
        load_h, unload_h
    """
    return _od_fetch("transportlogisticsreport", orig_lga, dest_lga, mode)


# ---------------------------------------------------------------------------
# New: densitymap destination view — all destinations from an origin
# ---------------------------------------------------------------------------

def fetch_origin_destinations(
    orig_lga: str,
    mode: str | None = "road",
) -> tuple[list[dict], str | None]:
    """
    Fetch all destinations reachable from an origin (densitymap endpoint).

    Used for OD corridor rankings on Page 2.
    Note: densitymap numbers differ from commodityreport — different pipelines.

    Returns records with fields:
        dest_lga, name, trips, tonnes, trailer_loads, tonnes_per_trailer,
        avg_trip_distance, avg_trip_duration, total_trip_distance,
        total_trip_duration, trip_transport_costs, total_freight_value,
        cst_per_tonne, cst_per_tonne_km, co2_tn
    """
    p = {
        "dataset":              "SIM-AU-BASELINE",
        "metric":               "cst_per_tonne",
        "value_type":           "total",
        "local_trips":          "true",
        "regions":              "dest_lga",
        "orig_region_category": "orig_lga",
        "orig_region":          orig_lga,
    }
    if mode:
        p["mode"] = mode
    url = f"{_BASE}/densitymap?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = json.load(resp)
        return (raw if isinstance(raw, list) else []), None
    except urllib.error.URLError as exc:
        return [], f"Network error: {exc.reason}"
    except json.JSONDecodeError:
        return [], "API returned invalid JSON."


# ---------------------------------------------------------------------------
# New: local data loader — reads pre-downloaded offline JSON
# ---------------------------------------------------------------------------

LOCAL_DATA_ROOT    = pathlib.Path(__file__).parent / "api_local_data" / "level2"
LOCAL_DATA_ROOT_L3 = pathlib.Path(__file__).parent / "api_local_data" / "level3"


def load_local_origin_data(
    orig_lga: str,
    orig_state: str,
) -> tuple[dict | None, str | None]:
    """
    Load pre-downloaded commodityreport data for all destinations of an origin.

    Reads from:
        ../commodity_freightod_explorer_offline_local_data/local_data/<STATE>/<LGA>.json

    File structure:
        {"destinations": {"LGA_XXXXX": [commodity_records...], ...}}

    Returns:
        (
            {dest_lga: totals_dict, ...},  # None if file not found
            error_string_or_None
        )
    """
    path = LOCAL_DATA_ROOT / orig_state / f"{orig_lga}.json"
    if not path.exists():
        return None, f"Local data not found at: {path}\nRun fetch_all_data.py in commodity_freightod_explorer_offline_local_data/ first."

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"Failed to read local file: {exc}"

    destinations = data.get("destinations", {})
    result: dict[str, dict] = {}
    for dest_lga, records in destinations.items():
        if records:
            result[dest_lga] = _compute_totals(
                records, is_local=(orig_lga == dest_lga)
            )
    return result, None


def load_all_od_pairs() -> tuple[list[dict], str | None]:
    """
    Load ALL pre-downloaded commodityreport data across every origin in local_data/.

    Iterates all state subdirectories and JSON files under LOCAL_DATA_ROOT.

    Returns:
        (
            [{"orig_lga", "orig_state", "dest_lga", "tonnes", "cost_per_tonne",
              "transport_cost", "freight_value", "co2", "trips", "avg_distance"}, ...],
            error_string_or_None
        )
    """
    if not LOCAL_DATA_ROOT.exists():
        return [], (
            f"Local data directory not found: {LOCAL_DATA_ROOT}\n"
            "Run fetch_all_data.py in commodity_freightod_explorer_offline_local_data/ first."
        )

    rows: list[dict] = []
    for state_dir in sorted(LOCAL_DATA_ROOT.iterdir()):
        if not state_dir.is_dir():
            continue
        state = state_dir.name
        for json_file in sorted(state_dir.glob("*.json")):
            orig_lga = json_file.stem
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            for dest_lga, records in data.get("destinations", {}).items():
                if records:
                    t = _compute_totals(records, is_local=(orig_lga == dest_lga))
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
        return [], "No local data found. Run fetch_all_data.py first."
    return rows, None


# ---------------------------------------------------------------------------
# Level 3 local data loaders (api_local_data/level3/)
# Records include a "commodity" field (individual commodity name, e.g. "Beer")
# in addition to "industry" (Level 2 group) and "sector".
# ---------------------------------------------------------------------------

def load_local_origin_data_l3(
    orig_lga: str,
    orig_state: str,
) -> tuple[dict | None, str | None]:
    """
    Load pre-downloaded Level 3 commodityreport data for all destinations of an origin.
    Records include a 'commodity' field (e.g. "Beer", "Milk") alongside 'industry'.
    Reads from: api_local_data/level3/<STATE>/<LGA>.json
    Returns: ({dest_lga: totals_dict, ...}, error_or_None)
    """
    path = LOCAL_DATA_ROOT_L3 / orig_state / f"{orig_lga}.json"
    if not path.exists():
        return None, f"Level 3 local data not found at: {path}"

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"Failed to read Level 3 local file: {exc}"

    result: dict[str, dict] = {}
    for dest_lga, records in data.get("destinations", {}).items():
        if records:
            result[dest_lga] = _compute_totals(records, is_local=(orig_lga == dest_lga))
    return result, None


def load_all_od_pairs_l3() -> tuple[list[dict], str | None]:
    """
    Load ALL pre-downloaded Level 3 commodityreport data across every origin.
    Iterates all state subdirectories under LOCAL_DATA_ROOT_L3.
    Returns flat list of OD pair dicts (same schema as load_all_od_pairs()).
    """
    if not LOCAL_DATA_ROOT_L3.exists():
        return [], f"Level 3 local data directory not found: {LOCAL_DATA_ROOT_L3}"

    rows: list[dict] = []
    for state_dir in sorted(LOCAL_DATA_ROOT_L3.iterdir()):
        if not state_dir.is_dir():
            continue
        state = state_dir.name
        for json_file in sorted(state_dir.glob("*.json")):
            orig_lga = json_file.stem
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            for dest_lga, records in data.get("destinations", {}).items():
                if records:
                    t = _compute_totals(records, is_local=(orig_lga == dest_lga))
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
        return [], "No Level 3 local data found. Use the download panel to fetch it."
    return rows, None
