"""Plant thresholds and health evaluation."""

from .db import query_all, query_one
from .sensors import METRICS

# Metric key -> the min/max column pair holding its safe range.
THRESHOLD_COLUMNS = {
    "temperature": ("temp_min", "temp_max"),
    "humidity": ("humid_min", "humid_max"),
    "moisture": ("moist_min", "moist_max"),
    "light": ("light_intense_min", "light_intense_max"),
    "voc": ("VOC_min", "VOC_max"),
    "co2": ("CO2_min", "CO2_max"),
}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_plant(name: str):
    if not name:
        return None
    return query_one(
        "SELECT * FROM plants WHERE plant_name = ? COLLATE NOCASE", (name,)
    )


def list_plants() -> list:
    return query_all("SELECT plant_name FROM plants ORDER BY plant_name")


def thresholds_for(plant) -> dict:
    """``{metric_key: (min, max)}`` for a plant row, skipping unusable values."""
    if plant is None:
        return {}
    ranges = {}
    for key, (low_col, high_col) in THRESHOLD_COLUMNS.items():
        low = _to_float(plant[low_col])
        high = _to_float(plant[high_col])
        if low is None or high is None:
            continue
        ranges[key] = (low, high)
    return ranges


def evaluate(plant, latest: dict) -> list:
    """Compare the newest reading against a plant's safe range.

    Returns one row per metric with the value, its range and a status of
    ``ok``, ``alert`` or ``unknown`` (missing reading or missing threshold).
    """
    ranges = thresholds_for(plant)
    latest = latest or {}
    rows = []
    for metric in METRICS:
        key = metric["key"]
        value = latest.get(key)
        bounds = ranges.get(key)
        if value is None or bounds is None:
            status = "unknown"
        elif bounds[0] <= value <= bounds[1]:
            status = "ok"
        else:
            status = "alert"
        rows.append(
            {
                "key": key,
                "label": metric["label"],
                "unit": metric["unit"],
                "value": value,
                "min": bounds[0] if bounds else None,
                "max": bounds[1] if bounds else None,
                "status": status,
            }
        )
    return rows


def health_summary(rows: list) -> dict:
    """Counts plus a single headline status for the evaluated rows."""
    counts = {"ok": 0, "alert": 0, "unknown": 0}
    for row in rows:
        counts[row["status"]] += 1
    if counts["alert"]:
        overall = "alert"
    elif counts["ok"]:
        overall = "ok"
    else:
        overall = "unknown"
    return {"counts": counts, "overall": overall, "tracked": len(rows)}
