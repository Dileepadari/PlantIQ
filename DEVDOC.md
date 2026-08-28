# PlantIQ - Developer Documentation

Technical reference for the PlantIQ codebase: architecture, auth, data model,
API surface, setup and deployment. For what the app does from a user's point of
view, see [README.md](./README.md).

## Table of contents

- [Tech stack](#tech-stack)
- [Layout](#layout)
- [Architecture](#architecture)
- [Application factory](#application-factory)
- [Auth model](#auth-model)
- [Data model](#data-model)
- [Sensor feed](#sensor-feed)
- [Threshold evaluation](#threshold-evaluation)
- [API surface](#api-surface)
- [Frontend](#frontend)
- [Charts](#charts)
- [Theming](#theming)
- [Environment variables](#environment-variables)
- [Local development](#local-development)
- [Deployment](#deployment)
- [Firmware](#firmware)
- [Gotchas](#gotchas)

## Tech stack

Flask 3 + Jinja templates, SQLite, `requests` for the ThingSpeak API. No ORM, no
migrations tool, no build step. The frontend is hand-written CSS and vanilla
JavaScript with zero runtime dependencies - no Bootstrap, no jQuery, no charting
library. Everything is served from `src/static`, so the app works offline apart
from the sensor feed itself.

## Layout

```
src/
  wsgi.py                 entry point; creates the app
  Database.db             SQLite file (committed - carries the plant profiles)
  plantiq/
    __init__.py           create_app(), error handlers, template filters
    config.py             every setting, all env-overridable
    db.py                 connection per request, schema bootstrap
    security.py           password hashing plus legacy-row upgrade
    sensors.py            ThingSpeak client, field mapping, caching
    plants.py             threshold lookup and evaluation
    notifications.py      alert storage and relative ages
    auth.py               blueprint: login, signup, logout, login_required
    views.py              blueprint: the signed-in pages
    api.py                blueprint: JSON for the browser and the device
  templates/              layout.html + one file per page, _-prefixed partials
  static/
    css/app.css           the whole design system
    js/charts.js          SVG chart renderer
    js/app.js             theme, mobile nav, live refresh
    images/
Arduino/ESW_Project.ino   firmware
OM2M_ESW/                 OM2M middlenode (git submodule)
```

## Architecture

```
  ESP32  ──MQTT──▶  ThingSpeak channel
    │                     │
    │ HTTP POST           │ HTTP GET (cached 20s)
    │ /api/alerts         ▼
    └──────────────▶  Flask app ──▶ SQLite (users, plants, notifications)
                          │
                          ▼
                      Browser (Jinja pages + /api/* JSON)
```

The device is the only writer of sensor data, and it writes to ThingSpeak, not
to this app. PlantIQ owns three things: accounts, the per-species threshold
profiles, and the alert log. It never stores a sensor reading, which is why
there is no ingest endpoint for readings and no table for them.

## Application factory

`plantiq.create_app()` builds the app, registers the three blueprints, wires
`teardown_appcontext` to close the request's SQLite connection, and runs
`init_db()` once so a fresh checkout works without a setup step. `wsgi.py` calls
it and exposes `app`.

Templates and static files live one level above the package, so the factory
passes explicit `template_folder="../templates"` and `static_folder="../static"`.

Error handlers render `error.html` for pages and return JSON for anything under
`/api/` or any request with a JSON body.

## Auth model

Sessions are Flask's signed cookie holding a single `user_id`. `auth.current_user()`
loads the row once per request onto `g`; `@login_required` redirects to
`/login?next=<path>` when there is none, and `_safe_next()` refuses anything that
is not a same-site relative path.

**Passwords are hashed** with Werkzeug's `generate_password_hash` (scrypt).
The original database stored them in clear text, so `security.verify_password()`
accepts both: if the stored value does not start with a known digest prefix it
falls back to a string compare, and `auth.login` then rewrites that row as a
hash. Clear-text rows therefore upgrade themselves the first time each user
signs in, with no migration script and no forced reset.

Username and email are immutable after signup - the settings form renders them
disabled and the POST handler never reads them.

## Data model

Three tables, created by `db.SCHEMA` if missing.

**`users`** - `Userid`, `username`, `email`, `password` (scrypt hash),
`Name`, `pro_img`, `plant`, `reading_no`. Unique indexes on `username` and
`email`. `plant` is a free-text species name matched case-insensitively against
`plants.plant_name`; `reading_no` is the chart window, clamped to
`MIN_READINGS`..`MAX_READINGS` on both read and write.

**`plants`** - `plant_id`, `plant_name`, and a `_min`/`_max` pair per metric:
`VOC`, `temp`, `humid`, `moist`, `CO2`, `light_intense`. This is the reference
data the app is useless without, which is why `Database.db` is committed.

**`notifications`** - `notification_id`, `plant_name`, `msg`, `notif_type`
(`success` / `info` / `warning` / `danger`), `date_time` (`%d-%m-%Y %H:%M`),
`status` (0 open, 1 dismissed). Indexed on `status`.

Every query is parameterised. There are no f-string or `.format()` SQL strings
anywhere in the package; the previous version built queries by concatenation and
was injectable through the login form and the settings form.

## Sensor feed

`sensors.py` owns the only knowledge of ThingSpeak field numbering:

| Field | Metric | Unit |
|---|---|---|
| field1 | temperature | C |
| field2 | moisture | % |
| field3 | light | % |
| field4 | voc | ppb |
| field5 | co2 | ppm |
| field6 | humidity | % |

`FIELD_MAP` translates a raw feed entry into named keys; `METRICS` carries the
display metadata (label, unit, nominal max, accent) that drives the dashboard
tiles and the statistics charts, so adding a sensor is a one-list change.

Two entry points, both of which **never raise**: `fetch_readings(count)` for the
newest N readings and `fetch_range(start, end)` for a date window. A failed or
slow call returns `{"readings": [], "online": False}` and the page renders with
an offline banner. `fetch_readings` is cached in-process for
`THINGSPEAK_CACHE_TTL` seconds keyed on the count, so a page with six charts
makes one HTTP call.

`_is_stale()` / `_age_of()` report how old the newest reading is. Anything older
than an hour is flagged, and the UI then says "latest readings, recorded N ago"
instead of "live conditions".

## Threshold evaluation

`plants.evaluate(plant_row, latest_reading)` returns one row per metric with
`value`, `min`, `max` and a `status` of `ok`, `alert` or `unknown`. `unknown`
covers both a missing reading and a missing threshold, which is why it is a
third state rather than a boolean - a sensor that did not report is not the same
as a sensor that is out of range. `health_summary()` folds those into counts
plus a single headline status.

## API surface

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/readings?count=N` | session | Latest values, per-metric series, evaluated rows, summary |
| GET | `/api/history?start=&end=` | session | Readings in a date range, plus `latest_available` when empty |
| GET | `/api/alerts` | session | Open alerts as JSON |
| POST | `/api/alerts` | device token | Ingest an alert from the firmware |
| POST | `/receive` | device token | Alias of the above, kept for deployed firmware |

The device authenticates with a shared token, sent either as `secret` in the
JSON body (what the current firmware does) or as an `X-Device-Token` header.
A duplicate of an already-open alert returns `200 {"status":"duplicate"}` rather
than creating a second row, so the firmware can retry freely.

**Removed:** the previous version exposed `POST /query`, which executed
arbitrary SQL from the request body behind the same shared secret. That is
remote code execution against the database for anyone who read the firmware
source, and there is no safe version of it, so it is gone rather than fixed.
Use `sqlite3 src/Database.db` for the maintenance it was doing.

## Frontend

`layout.html` is the shell: fixed sidebar, sticky top bar, flash messages, and a
`{% block content %}`. Page templates extend it and set `page_title` plus
`active` (the endpoint name, which marks the nav item).

**Width.** Three elements share one centred container of `--content-max`
(1560px): `.topbar-inner`, `.content` and `.page-foot-inner`. The top bar's
background and border still span the viewport, so the chrome is full-bleed while
its contents line up with the page beneath. Setting a `max-width` on `.content`
alone leaves it hugging the left edge with a dead gutter on wide screens, which
is what the first cut did.

Form fields cap at 460px (`.field > input`) so a half-width card does not
stretch a name field across 800px; `.form-row` fields sit at 220px, which is
what the date pickers want.

`views.inject_layout` is an `app_context_processor` supplying `user`, `nav`,
`unread`, `unread_count` and `metrics` to every template, so no view has to pass
them.

Two partial files, both `_`-prefixed so they read as non-routable:
`_icons.html` (an `icon(name)` macro over a dict of inline SVG paths - there is
no icon font) and `_partials.html` (metric tile, status pill, feed banner, empty
state).

Auth pages extend `_auth_layout.html` instead, which has no sidebar.

## Charts

`static/js/charts.js` draws line/area charts into an SVG it builds itself. It is
about 200 lines and replaces Morris + Raphael + jQuery.

Usage is declarative: put `data-chart='[{"label":..,"value":..}]'` on a div, plus
optional `data-color`, `data-unit`, `data-height`, `data-label`. `app.js` mounts
every such node on load, keeps a registry, and redraws them on resize and on
theme change (colours are CSS variables, so a redraw is what re-reads them).

Axis ticks take their precision from the computed step, not the value's
magnitude, so a flat series near 400 prints `399.5, 400, 400.5` rather than
`400, 400, 400`.

`PlantIQ.setChartData(node, points)` swaps a series in place; the dashboard's
live refresh uses it via the `data-series` attribute.

## Theming

All colour lives in CSS custom properties in `static/css/app.css`, defined three
times: on bare `:root` (light), under
`@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }`, and
under `:root[data-theme="dark"]`. That third block is what makes an explicit
toggle beat the system preference in both directions.

An inline script in `<head>` reads `localStorage['plantiq-theme']` and stamps
`data-theme` before first paint, so there is no flash. Every storage access is
wrapped in try/catch for private-mode browsers.

The ADK DEV mark is a single purple-on-transparent PNG. `.logo-mono` applies
`filter: brightness(0)` in light and `brightness(0) invert(1)` in dark rather
than shipping two files.

## Environment variables

Copy `.env.example` to `.env`. Everything has a working default except the two
secrets, which must be set before deploying anywhere public.

| Variable | Default | Purpose |
|---|---|---|
| `PLANTIQ_SECRET_KEY` | `dev-only-change-me` | Signs the session cookie |
| `PLANTIQ_DEVICE_TOKEN` | the original hardcoded string | Shared secret for alert ingest |
| `PLANTIQ_DATABASE` | `src/Database.db` | Absolute path to the SQLite file |
| `PLANTIQ_TS_CHANNEL` | `2281910` | ThingSpeak channel id |
| `PLANTIQ_TS_READ_KEY` | the project's key | ThingSpeak read API key |
| `PLANTIQ_TS_TIMEZONE` | `Asia/Kolkata` | Timezone for returned timestamps |
| `PLANTIQ_TS_TIMEOUT` | `6` | HTTP timeout in seconds |
| `PLANTIQ_TS_CACHE_TTL` | `20` | Seconds a fetched feed is reused |
| `PLANTIQ_HOST` / `PLANTIQ_PORT` | `127.0.0.1` / `5000` | Dev server bind |
| `PLANTIQ_DEBUG` | `1` | Dev server reloader and traceback page |

The defaults reproduce the original deployment. They are checked in because this
is a coursework repo whose ThingSpeak channel is public and whose device token
is readable in the committed firmware; treat both as already disclosed and set
your own if you redeploy.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/wsgi.py
```

Then open http://127.0.0.1:5000. The schema is created on first run; the
committed `Database.db` already has the plant profiles and a demo account.

To reset a password or add a plant profile, use the module directly:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from plantiq import create_app
from plantiq.db import execute
from plantiq.security import hash_password
with create_app().app_context():
    execute('UPDATE users SET password = ? WHERE email = ?',
            (hash_password('newpassword'), 'someone@example.com'))
"
```

## Deployment

Any WSGI host. `wsgi.py` exposes `app`:

```bash
gunicorn --chdir src wsgi:app
```

On PythonAnywhere, point the WSGI configuration file at `src/wsgi.py` and its
`app`, and set `PLANTIQ_SECRET_KEY` and `PLANTIQ_DEVICE_TOKEN` in the web app's
environment. The SQLite file must be on a writable path.

## Firmware

`Arduino/ESW_Project.ino` runs on the ESP32. Before flashing, change `CSE_IP` to
the machine running OM2M, the wifi SSID and password, and the ThingSpeak channel
id and MQTT credentials. The alert URL near the bottom of the file must point at
your deployment; `/receive` and `/api/alerts` both work.

OM2M is a submodule - `git submodule update --init` then run
`OM2M_ESW/eclipse-om2m-v1-4-1/in-cse/start.sh`.

## Gotchas

- **ThingSpeak sends the string `"NaN"`** when a sensor did not report. `float()`
  accepts it, and a bare `NaN` is not valid JSON, so `jsonify` produces a body
  that `JSON.parse` rejects and the whole response fails. `sensors._to_float`
  filters non-finite values to `None`. Do not remove that check.
- **`input.valueAsDate` reads and writes UTC.** Setting it from a locally
  constructed midnight shifts the displayed day for anyone not on UTC. The
  History page formats a local `YYYY-MM-DD` string and assigns `.value` instead.
- **The channel's data ends 2023-11-21.** The hardware is not running, so the
  dashboard is permanently in its stale state. That is the honest rendering, not
  a bug; point `PLANTIQ_TS_CHANNEL` at a live channel to see the other path.
- **`reading_no` is clamped on read as well as write.** An old row can hold a
  value outside the current bounds, and an unclamped one goes straight into a
  ThingSpeak `results` parameter.
- **The metric accent key is `temp`, not `temperature`** (`METRICS[0]["accent"]`),
  because it names the CSS variable `--c-temp`. The tile selector in `app.css`
  must match that string, not the metric key.
- **Alert dismissal is a POST**, not the old `GET /change_seen/<id>` link, so a
  crawler or a prefetch cannot clear someone's alerts.
