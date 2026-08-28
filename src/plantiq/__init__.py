"""PlantIQ - Flask application factory.

The app is assembled from three blueprints: ``auth`` (sign-in), ``views``
(the signed-in pages) and ``api`` (JSON for the browser and the ESP32).
"""

from flask import Flask, jsonify, render_template

from .config import Config

__version__ = "2.0.0"


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(config_object)

    from . import api, auth, db, views

    db.close_db  # noqa: B018 - referenced for clarity
    app.teardown_appcontext(db.close_db)

    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)
    app.register_blueprint(api.bp)

    # The deployed firmware posts alerts to /receive. Keep that path working.
    app.add_url_rule(
        "/receive", endpoint="legacy_receive", view_func=api.ingest_alert,
        methods=["POST"],
    )

    with app.app_context():
        db.init_db()

    @app.template_filter("metric")
    def _format_metric(value, unit=""):
        """Render a reading, or an em-free placeholder when it is missing."""
        if value is None:
            return "--"
        text = f"{value:g}" if isinstance(value, float) else str(value)
        return f"{text}{unit}" if unit else text

    @app.errorhandler(404)
    def _not_found(error):
        if _wants_json():
            return jsonify({"status": "error", "message": "not found"}), 404
        return render_template("error.html", code=404,
                               message="That page does not exist."), 404

    @app.errorhandler(500)
    def _server_error(error):
        app.logger.exception("Unhandled error")
        if _wants_json():
            return jsonify({"status": "error", "message": "server error"}), 500
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500

    return app


def _wants_json() -> bool:
    from flask import request

    return request.path.startswith("/api/") or request.is_json
