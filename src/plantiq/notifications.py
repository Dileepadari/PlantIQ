"""Alerts raised by the firmware and shown in the UI."""

from datetime import datetime

from .db import execute, query_all

DATE_FORMAT = "%d-%m-%Y %H:%M"

# notif_type values the UI knows how to style. Anything else falls back to info.
KNOWN_TYPES = {"success", "info", "warning", "danger"}


def _relative_age(stamp: str) -> str:
    try:
        recorded = datetime.strptime(stamp, DATE_FORMAT)
    except (TypeError, ValueError):
        return ""
    delta = datetime.now() - recorded
    if delta.days >= 1:
        return f"{delta.days}d"
    hours = delta.seconds // 3600
    if hours:
        return f"{hours}h"
    minutes = delta.seconds // 60
    if minutes:
        return f"{minutes}m"
    return f"{max(delta.seconds, 0)}s"


def _shape(row) -> dict:
    notif_type = (row["notif_type"] or "info").lower()
    return {
        "id": row["notification_id"],
        "plant": row["plant_name"],
        "message": row["msg"],
        "type": notif_type if notif_type in KNOWN_TYPES else "info",
        "recorded_at": row["date_time"],
        "age": _relative_age(row["date_time"]),
    }


def unread(limit: int = None) -> list:
    sql = (
        "SELECT * FROM notifications WHERE status = 0 "
        "ORDER BY notification_id DESC"
    )
    params = ()
    if limit:
        sql += " LIMIT ?"
        params = (limit,)
    return [_shape(row) for row in query_all(sql, params)]


def mark_seen(notification_id: int) -> None:
    execute(
        "UPDATE notifications SET status = 1 WHERE notification_id = ?",
        (notification_id,),
    )


def mark_all_seen() -> None:
    execute("UPDATE notifications SET status = 1 WHERE status = 0")


def record(plant_name: str, message: str, notif_type: str = "warning") -> bool:
    """Store an alert. Returns False when the same one is already pending."""
    duplicate = query_all(
        "SELECT 1 FROM notifications "
        "WHERE status = 0 AND plant_name = ? AND msg = ? LIMIT 1",
        (plant_name, message),
    )
    if duplicate:
        return False
    execute(
        "INSERT INTO notifications (plant_name, msg, notif_type, date_time) "
        "VALUES (?, ?, ?, ?)",
        (plant_name, message, notif_type, datetime.now().strftime(DATE_FORMAT)),
    )
    return True
