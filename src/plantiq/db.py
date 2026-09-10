"""SQLite access helpers, the schema, and the reference data that seeds it.

One connection per request, stored on Flask's ``g``, closed automatically when
the request ends. Rows come back as ``sqlite3.Row`` so templates and views can
use column names instead of positional indexes.

The database file itself is **not** in the repository. It used to be, which is
how six people's names, email addresses and clear-text passwords ended up
published. What the app actually needs from it is the plant threshold table, and
that lives in ``data/plants.json`` where a diff can read it.
"""

import json
import sqlite3
from pathlib import Path

from flask import current_app, g

DATA_DIR = Path(__file__).resolve().parent / "data"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql: str, params: tuple = ()) -> list:
    return get_db().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()):
    return get_db().execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    db = get_db()
    cursor = db.execute(sql, params)
    db.commit()
    return cursor


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    Userid      INTEGER NOT NULL PRIMARY KEY,
    username    TEXT    NOT NULL COLLATE NOCASE,
    email       TEXT    NOT NULL COLLATE NOCASE,
    password    TEXT    NOT NULL,
    Name        TEXT    NOT NULL COLLATE NOCASE,
    pro_img     TEXT    DEFAULT 'images/profile.png',
    plant       TEXT    COLLATE NOCASE,
    reading_no  INTEGER NOT NULL DEFAULT 10
);

CREATE TABLE IF NOT EXISTS plants (
    plant_id            INTEGER NOT NULL PRIMARY KEY,
    plant_name          TEXT    NOT NULL,
    VOC_min             INTEGER,
    VOC_max             INTEGER,
    temp_min            INTEGER,
    temp_max            INTEGER,
    humid_min           INTEGER,
    humid_max           INTEGER,
    moist_min           INTEGER,
    moist_max           INTEGER,
    CO2_min             INTEGER,
    CO2_max             INTEGER,
    light_intense_min   INTEGER,
    light_intense_max   INTEGER
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    plant_name      TEXT,
    msg             TEXT,
    notif_type      TEXT    NOT NULL DEFAULT 'error',
    date_time       TEXT    NOT NULL,
    status          INTEGER DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email    ON users (email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX        IF NOT EXISTS idx_notif_status   ON notifications (status);
"""


PLANT_COLUMNS = (
    "plant_name", "VOC_min", "VOC_max", "temp_min", "temp_max",
    "humid_min", "humid_max", "moist_min", "moist_max",
    "CO2_min", "CO2_max", "light_intense_min", "light_intense_max",
)


def load_plants() -> list:
    """The shipped plant threshold profiles."""
    return json.loads((DATA_DIR / "plants.json").read_text())


def seed_plants() -> int:
    """Insert any shipped plant the database does not already have.

    Matched by name rather than id, so re-running never duplicates a row and
    never overwrites a threshold someone tuned for their own greenhouse.
    """
    db = get_db()
    existing = {row["plant_name"] for row in db.execute("SELECT plant_name FROM plants")}
    added = 0
    for plant in load_plants():
        if plant["plant_name"] in existing:
            continue
        db.execute(
            f"INSERT INTO plants ({', '.join(PLANT_COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(PLANT_COLUMNS))})",
            tuple(plant[column] for column in PLANT_COLUMNS),
        )
        added += 1
    db.commit()
    return added


def init_db() -> None:
    """Create any missing table or index, then top up the plant profiles.

    Safe to run on an existing file, and run on every start, so a fresh checkout
    with no database file becomes a working install without a separate step.
    """
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    seed_plants()
