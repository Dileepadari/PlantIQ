"""Application configuration.

Every value can be overridden with an environment variable so the same code
runs unchanged on a laptop and on a host such as PythonAnywhere.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # Flask
    SECRET_KEY = os.environ.get("PLANTIQ_SECRET_KEY", "dev-only-change-me")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Storage. Absolute, so the app works from any working directory.
    DATABASE = os.environ.get("PLANTIQ_DATABASE", str(BASE_DIR / "Database.db"))

    # ThingSpeak channel that the ESP32 publishes to.
    THINGSPEAK_CHANNEL = os.environ.get("PLANTIQ_TS_CHANNEL", "2281910")
    THINGSPEAK_READ_KEY = os.environ.get("PLANTIQ_TS_READ_KEY", "1M6NTVUZOV87FRI0")
    THINGSPEAK_TIMEZONE = os.environ.get("PLANTIQ_TS_TIMEZONE", "Asia/Kolkata")
    THINGSPEAK_TIMEOUT = _env_int("PLANTIQ_TS_TIMEOUT", 6)
    # Seconds a fetched feed is reused before hitting the API again.
    THINGSPEAK_CACHE_TTL = _env_int("PLANTIQ_TS_CACHE_TTL", 20)

    # Shared secret the firmware presents when POSTing an alert to /api/alerts.
    DEVICE_TOKEN = os.environ.get("PLANTIQ_DEVICE_TOKEN", "secretanicheppaga")

    # Bounds accepted for the "readings in charts" preference.
    MIN_READINGS = 5
    MAX_READINGS = 200
