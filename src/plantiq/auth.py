"""Sign-up, sign-in and the ``login_required`` guard."""

import functools
import re

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .db import execute, query_one
from .security import hash_password, is_hashed, verify_password

bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def current_user():
    """The signed-in user row, loaded once per request."""
    if "user" not in g:
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = query_one("SELECT * FROM users WHERE Userid = ?", (user_id,))
            if g.user is None:
                session.pop("user_id", None)
    return g.user


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _safe_next(target: str) -> str:
    """Only allow same-site relative redirects after login."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("views.dashboard")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(url_for("views.dashboard"))

    error = None
    if request.method == "POST":
        identifier = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_one(
            "SELECT * FROM users WHERE email = ? OR username = ? COLLATE NOCASE",
            (identifier, identifier),
        )
        if user and verify_password(user["password"], password):
            # Opportunistically upgrade a legacy clear-text row.
            if not is_hashed(user["password"]):
                execute(
                    "UPDATE users SET password = ? WHERE Userid = ?",
                    (hash_password(password), user["Userid"]),
                )
            session.clear()
            session["user_id"] = user["Userid"]
            return redirect(_safe_next(request.args.get("next", "")))
        error = "That email or password is not right."

    return render_template("login.html", error=error)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user() is not None:
        return redirect(url_for("views.dashboard"))

    error = None
    form = {}
    if request.method == "POST":
        form = {key: request.form.get(key, "").strip() for key in request.form}
        username = form.get("username", "")
        email = form.get("email", "")
        password = request.form.get("password", "")
        name = form.get("name", "")
        plant = form.get("plant", "")
        readings = form.get("init_read", "10")

        if not all([username, email, password, name]):
            error = "Username, name, email and password are all required."
        elif not EMAIL_RE.match(email):
            error = "That does not look like an email address."
        elif len(password) < 6:
            error = "Use a password of at least 6 characters."
        elif query_one(
            "SELECT 1 FROM users WHERE username = ? OR email = ?", (username, email)
        ):
            error = "An account with that username or email already exists."

        if error is None:
            try:
                readings = max(5, min(int(readings or 10), 200))
            except ValueError:
                readings = 10
            cursor = execute(
                "INSERT INTO users (username, email, password, Name, plant, reading_no) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (username, email, hash_password(password), name, plant, readings),
            )
            session.clear()
            session["user_id"] = cursor.lastrowid
            flash(f"Welcome to PlantIQ, {name}.", "success")
            return redirect(url_for("views.dashboard"))

    return render_template("signup.html", error=error, form=form)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
