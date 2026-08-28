"""The signed-in pages."""

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from . import notifications, plants, sensors
from .auth import current_user, login_required
from .db import execute

bp = Blueprint("views", __name__)

# Nav entries, rendered by the sidebar and used to mark the active page.
NAV = [
    {"endpoint": "views.dashboard",  "label": "Dashboard",  "icon": "grid"},
    {"endpoint": "views.statistics", "label": "Statistics", "icon": "chart"},
    {"endpoint": "views.analysis",   "label": "Analysis",   "icon": "gauge"},
    {"endpoint": "views.history",    "label": "History",    "icon": "clock"},
    {"endpoint": "views.alerts",     "label": "Alerts",     "icon": "bell"},
    {"endpoint": "views.circuit",    "label": "Circuit",    "icon": "chip"},
    {"endpoint": "views.about",      "label": "About",      "icon": "info"},
    {"endpoint": "views.settings",   "label": "Settings",   "icon": "cog"},
]


@bp.app_context_processor
def inject_layout():
    """Values every signed-in template needs: user, nav, unread alerts."""
    user = current_user()
    unread = notifications.unread() if user else []
    return {
        "user": user,
        "nav": NAV,
        "unread": unread,
        "unread_count": len(unread),
        "metrics": sensors.METRICS,
    }


def _reading_count(user) -> int:
    try:
        count = int(user["reading_no"])
    except (TypeError, ValueError, KeyError):
        count = 10
    return max(
        current_app.config["MIN_READINGS"],
        min(count, current_app.config["MAX_READINGS"]),
    )


@bp.route("/")
@login_required
def dashboard():
    user = current_user()
    feed = sensors.fetch_readings(_reading_count(user))
    plant = plants.get_plant(user["plant"])
    rows = plants.evaluate(plant, feed["latest"])
    return render_template(
        "dashboard.html",
        active="views.dashboard",
        feed=feed,
        plant=plant,
        rows=rows,
        summary=plants.health_summary(rows),
        chart=sensors.series(feed["readings"], "voc"),
    )


@bp.route("/statistics")
@login_required
def statistics():
    user = current_user()
    count = _reading_count(user)
    feed = sensors.fetch_readings(count)
    charts = [
        {
            "metric": metric,
            "points": sensors.series(feed["readings"], metric["key"]),
        }
        for metric in sensors.METRICS
    ]
    return render_template(
        "statistics.html",
        active="views.statistics",
        feed=feed,
        charts=charts,
        count=count,
    )


@bp.route("/analysis")
@login_required
def analysis():
    user = current_user()
    feed = sensors.fetch_readings(_reading_count(user))
    plant = plants.get_plant(user["plant"])
    rows = plants.evaluate(plant, feed["latest"])
    return render_template(
        "analysis.html",
        active="views.analysis",
        feed=feed,
        plant=plant,
        rows=rows,
        summary=plants.health_summary(rows),
        known_plants=plants.list_plants(),
    )


@bp.route("/history")
@login_required
def history():
    return render_template("history.html", active="views.history")


@bp.route("/alerts")
@login_required
def alerts():
    return render_template(
        "alerts.html", active="views.alerts", alerts=notifications.unread()
    )


@bp.route("/alerts/<int:notification_id>/dismiss", methods=["POST"])
@login_required
def dismiss_alert(notification_id):
    notifications.mark_seen(notification_id)
    return redirect(url_for("views.alerts"))


@bp.route("/alerts/dismiss-all", methods=["POST"])
@login_required
def dismiss_all_alerts():
    notifications.mark_all_seen()
    flash("All alerts cleared.", "success")
    return redirect(url_for("views.alerts"))


@bp.route("/circuit")
@login_required
def circuit():
    return render_template("circuit.html", active="views.circuit")


@bp.route("/about")
@login_required
def about():
    return render_template("about.html", active="views.about")


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = current_user()
    error = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        plant_name = request.form.get("plant", "").strip()
        readings = request.form.get("reading", "").strip()

        try:
            readings = int(readings)
        except ValueError:
            error = "Number of readings must be a whole number."
        else:
            low = current_app.config["MIN_READINGS"]
            high = current_app.config["MAX_READINGS"]
            if not name:
                error = "Name cannot be empty."
            elif not low <= readings <= high:
                error = f"Number of readings must be between {low} and {high}."
            elif plants.get_plant(plant_name) is None:
                error = f"'{plant_name}' is not in the plant database yet."

        if error is None:
            execute(
                "UPDATE users SET Name = ?, plant = ?, reading_no = ? WHERE Userid = ?",
                (name, plant_name, readings, user["Userid"]),
            )
            sensors.clear_cache()
            flash("Settings saved.", "success")
            return redirect(url_for("views.settings"))

    return render_template(
        "settings.html",
        active="views.settings",
        error=error,
        known_plants=plants.list_plants(),
    )
