"""JSON endpoints.

Two audiences: the browser (same-session reads that keep the dashboard live)
and the ESP32 firmware (alert ingest, authenticated with a shared token).
"""

from flask import Blueprint, current_app, jsonify, request

from . import notifications, plants, sensors
from .auth import current_user, login_required

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/readings")
@login_required
def readings():
    """Latest values plus per-metric series, used to refresh pages in place."""
    try:
        count = int(request.args.get("count", 20))
    except ValueError:
        count = 20
    count = max(
        current_app.config["MIN_READINGS"],
        min(count, current_app.config["MAX_READINGS"]),
    )

    feed = sensors.fetch_readings(count)
    user = current_user()
    plant = plants.get_plant(user["plant"])
    rows = plants.evaluate(plant, feed["latest"])

    return jsonify(
        {
            "online": feed["online"],
            "latest": feed["latest"],
            "series": {
                metric["key"]: sensors.series(feed["readings"], metric["key"])
                for metric in sensors.METRICS
            },
            "rows": rows,
            "summary": plants.health_summary(rows),
        }
    )


@bp.route("/history")
@login_required
def history():
    """Feed entries between two dates, for the History page table."""
    start = request.args.get("start")
    end = request.args.get("end")
    feed = sensors.fetch_range(start, end)

    # An empty range is usually the user guessing dates the device never ran.
    # Hand back the newest date on the channel so the page can point at it.
    latest_date = None
    if feed["online"] and not feed["readings"]:
        recent = sensors.fetch_readings(1)
        if recent["latest"]:
            latest_date = (recent["latest"]["recorded_at"] or "")[:10]

    return jsonify(
        {
            "online": feed["online"],
            "count": len(feed["readings"]),
            "readings": feed["readings"],
            "latest_available": latest_date,
        }
    )


@bp.route("/alerts")
@login_required
def alert_list():
    return jsonify({"alerts": notifications.unread(), "count": len(notifications.unread())})


@bp.route("/alerts", methods=["POST"])
def ingest_alert():
    """Device endpoint. The firmware POSTs here when a threshold is crossed."""
    payload = request.get_json(silent=True) or {}
    token = payload.get("secret") or request.headers.get("X-Device-Token")

    if token != current_app.config["DEVICE_TOKEN"]:
        return jsonify({"status": "error", "message": "invalid device token"}), 401

    message = (payload.get("msg") or "").strip()
    plant_name = (payload.get("plant_name") or "").strip()
    notif_type = (payload.get("notif_type") or "warning").strip().lower()

    if not message or not plant_name:
        return (
            jsonify({"status": "error", "message": "plant_name and msg are required"}),
            400,
        )
    if notif_type not in notifications.KNOWN_TYPES:
        notif_type = "warning"

    if notifications.record(plant_name, message, notif_type):
        return jsonify({"status": "success"}), 201
    return jsonify({"status": "duplicate", "message": "already pending"}), 200
