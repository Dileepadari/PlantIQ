"""SQLite access helpers.

One connection per request, stored on Flask's ``g``, closed automatically when
the request ends. Rows come back as ``sqlite3.Row`` so templates and views can
use column names instead of positional indexes.
"""

import sqlite3

from flask import current_app, g


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


def init_db() -> None:
    """Create any missing table or index. Safe to run on an existing file."""
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
