"""ThingSpeak client.

The ESP32 publishes six fields to a ThingSpeak channel. This module hides the
field numbering behind readable names, caches responses briefly so a page with
several panels causes one HTTP call, and never raises: if the API is slow or
unreachable the caller gets an empty reading set and the page still renders.
"""

import math
import threading
import time
from datetime import datetime

import requests
from flask import current_app

# ThingSpeak field number -> what the firmware writes into it.
FIELD_MAP = {
    "temperature": "field1",
    "moisture": "field2",
    "light": "field3",
    "voc": "field4",
    "co2": "field5",
    "humidity": "field6",
}

# Display metadata, also used to build the dashboard cards and the chart pages.
METRICS = [
    {"key": "temperature", "label": "Temperature", "unit": "C",   "field": 1, "max": 50,   "accent": "temp"},
    {"key": "humidity",    "label": "Humidity",    "unit": "%",   "field": 6, "max": 100,  "accent": "humidity"},
    {"key": "moisture",    "label": "Soil Moisture", "unit": "%", "field": 2, "max": 100,  "accent": "moisture"},
    {"key": "light",       "label": "Light Intensity", "unit": "%", "field": 3, "max": 100, "accent": "light"},
    {"key": "voc",         "label": "VOC",         "unit": "ppb", "field": 4, "max": 1000, "accent": "voc"},
    {"key": "co2",         "label": "CO2",         "unit": "ppm", "field": 5, "max": 2000, "accent": "co2"},
]

METRICS_BY_KEY = {m["key"]: m for m in METRICS}

_cache = {}
_cache_lock = threading.Lock()


def _to_float(value):
    """Parse a ThingSpeak field, treating a missing sensor as no reading.

    ThingSpeak writes the literal string "NaN" when a sensor did not report.
    ``float()`` happily accepts that, and a bare NaN is not valid JSON, so it
    has to be filtered here or it breaks every API response that carries it.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, 2)


def _parse_feed(feed: dict) -> dict:
    """Turn one raw ThingSpeak feed entry into named readings."""
    reading = {name: _to_float(feed.get(field)) for name, field in FIELD_MAP.items()}
    reading["recorded_at"] = feed.get("created_at")
    reading["label"] = _short_time(feed.get("created_at"))
    return reading


def _parse_stamp(created_at):
    if not created_at:
        return None
    try:
        return datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return None


def _short_time(created_at) -> str:
    """``HH:MM`` for a reading from today, otherwise ``DD Mon HH:MM``.

    Without the date, an archived channel looks live, which is the one thing a
    monitoring dashboard must never imply.
    """
    stamp = _parse_stamp(created_at)
    if stamp is None:
        return str(created_at or "")
    if stamp.date() == datetime.now().date():
        return stamp.strftime("%H:%M")
    return stamp.strftime("%d %b %H:%M")


def fetch_readings(count: int = 10) -> dict:
    """Return ``{"readings": [...], "latest": {...}|None, "online": bool}``.

    ``readings`` is oldest-first so charts can plot it directly. A failed call
    yields an empty list rather than an exception.
    """
    count = max(1, min(int(count), 8000))
    cache_key = count
    ttl = current_app.config["THINGSPEAK_CACHE_TTL"]

    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and time.time() - cached["at"] < ttl:
            return cached["payload"]

    channel = current_app.config["THINGSPEAK_CHANNEL"]
    url = f"https://api.thingspeak.com/channels/{channel}/feeds.json"
    params = {
        "results": count,
        "timezone": current_app.config["THINGSPEAK_TIMEZONE"],
        "api_key": current_app.config["THINGSPEAK_READ_KEY"],
    }

    payload = {
        "readings": [], "latest": None, "online": False,
        "error": None, "age": None, "stale": False,
    }
    try:
        response = requests.get(
            url, params=params, timeout=current_app.config["THINGSPEAK_TIMEOUT"]
        )
        response.raise_for_status()
        feeds = response.json().get("feeds") or []
        readings = [_parse_feed(feed) for feed in feeds]
        latest = readings[-1] if readings else None
        payload = {
            "readings": readings,
            "latest": latest,
            "online": True,
            "error": None,
            "age": _age_of(latest),
            "stale": _is_stale(latest),
        }
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("ThingSpeak fetch failed: %s", exc)
        payload["error"] = str(exc)

    with _cache_lock:
        _cache[cache_key] = {"at": time.time(), "payload": payload}
    return payload


# A reading older than this is shown as historic rather than current.
STALE_AFTER_SECONDS = 3600


def _is_stale(latest) -> bool:
    stamp = _parse_stamp(latest["recorded_at"]) if latest else None
    if stamp is None:
        return True
    return (datetime.now() - stamp).total_seconds() > STALE_AFTER_SECONDS


def _age_of(latest) -> str:
    """Human wording for how long ago the newest reading landed."""
    stamp = _parse_stamp(latest["recorded_at"]) if latest else None
    if stamp is None:
        return None
    delta = datetime.now() - stamp
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 90:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'' if hours == 1 else 's'} ago"
    days = seconds // 86400
    if days < 60:
        return f"{days} day{'' if days == 1 else 's'} ago"
    return stamp.strftime("%d %b %Y")


def series(readings: list, metric: str) -> list:
    """Extract one metric as ``[{"label": ..., "value": ...}]``, gaps dropped."""
    out = []
    for reading in readings:
        value = reading.get(metric)
        if value is not None:
            out.append({"label": reading["label"], "value": value})
    return out


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def fetch_range(start: str = None, end: str = None, limit: int = 8000) -> dict:
    """Feed entries between two ``YYYY-MM-DD`` dates. Never raises."""
    channel = current_app.config["THINGSPEAK_CHANNEL"]
    url = f"https://api.thingspeak.com/channels/{channel}/feeds.json"
    params = {
        "timezone": current_app.config["THINGSPEAK_TIMEZONE"],
        "api_key": current_app.config["THINGSPEAK_READ_KEY"],
        "results": limit,
    }
    if start:
        params["start"] = f"{start} 00:00:00"
    if end:
        params["end"] = f"{end} 23:59:59"

    try:
        response = requests.get(
            url, params=params, timeout=current_app.config["THINGSPEAK_TIMEOUT"]
        )
        response.raise_for_status()
        feeds = response.json().get("feeds") or []
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("ThingSpeak range fetch failed: %s", exc)
        return {"readings": [], "online": False, "error": str(exc)}

    readings = []
    for feed in feeds:
        reading = _parse_feed(feed)
        reading["label"] = _full_time(feed.get("created_at"))
        readings.append(reading)
    return {"readings": readings, "online": True, "error": None}


def _full_time(created_at) -> str:
    if not created_at:
        return ""
    try:
        stamp = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return str(created_at)
    return stamp.strftime("%d %b %Y, %H:%M")
