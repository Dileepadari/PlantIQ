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
- [Reference data and seeding](#reference-data-and-seeding)
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
- [Tests](#tests)
- [Continuous integration](#continuous-integration)
- [Documentation and screenshots](#documentation-and-screenshots)
- [Gotchas](#gotchas)
- [Contributors](#contributors)

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
data the app is useless without, and it ships as
[`src/plantiq/data/plants.json`](./src/plantiq/data/plants.json). See
[Reference data and seeding](#reference-data-and-seeding); **no database file is
in this repository, and none may be added.**

**`notifications`** - `notification_id`, `plant_name`, `msg`, `notif_type`
(`success` / `info` / `warning` / `danger`), `date_time` (`%d-%m-%Y %H:%M`),
`status` (0 open, 1 dismissed). Indexed on `status`.

Every query is parameterised. There are no f-string or `.format()` SQL strings
anywhere in the package; the previous version built queries by concatenation and
was injectable through the login form and the settings form.

## Reference data and seeding

`src/plantiq/data/plants.json` holds the six shipped species and their
thresholds. `db.seed_plants()` inserts any of them the database does not already
have, and `db.init_db()` calls it on every application start, so:

- a fresh checkout with no database file becomes a working install with no
  separate seeding step;
- adding a species to the JSON gets it into every existing install on the next
  restart;
- a threshold somebody tuned for their own greenhouse is **never** overwritten,
  because the match is on `plant_name` and existing rows are skipped.

### Why the JSON exists at all

`src/Database.db` used to be tracked, and `.gitignore` carried a comment
explaining that it had to be, because it held the plant profiles. It also held
the `users` table: six real people's names, email addresses and **clear-text
passwords**, published from October 2023 until September 2026.

The profiles were the only part of that file worth keeping, and they are 90 lines
of JSON that a diff can actually review. The rest should never have been in a
repository at all. `not_for_you.md` has the full account, and CI now fails if any
`.db` reappears.

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
| `PLANTIQ_DEVICE_TOKEN` | empty | Shared secret for alert ingest. **Empty rejects every alert**, which is the correct closed default |
| `PLANTIQ_DATABASE` | `src/Database.db` | Absolute path to the SQLite file. Created on first start; never committed |
| `PLANTIQ_TS_BASE_URL` | `https://api.thingspeak.com` | Feed host. Override to point at a stand-in that speaks the same JSON |
| `PLANTIQ_TS_CHANNEL` | `2281910` | ThingSpeak channel id |
| `PLANTIQ_TS_READ_KEY` | empty | ThingSpeak read API key. The default channel is public and readable without one |
| `PLANTIQ_TS_TIMEZONE` | `Asia/Kolkata` | Timezone for returned timestamps |
| `PLANTIQ_TS_TIMEOUT` | `6` | HTTP timeout in seconds |
| `PLANTIQ_TS_CACHE_TTL` | `20` | Seconds a fetched feed is reused |
| `PLANTIQ_HOST` / `PLANTIQ_PORT` | `127.0.0.1` / `5000` | Dev server bind |
| `PLANTIQ_DEBUG` | `1` | Dev server reloader and traceback page |

No secret has a real default any more. The device token and the read key were
both inlined once and are on the rotation list as disclosed; the code now reads
them from the environment and an unset device token closes the ingest endpoint
rather than opening it.

`PLANTIQ_TS_BASE_URL` exists so the app can be run against a local feed. That is
how the README screenshots are taken, and it means the dashboard can be
demonstrated without borrowing a real channel's readings.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python src/wsgi.py
```

Then open http://127.0.0.1:5000. The first run creates the schema and loads the
plant profiles. **No account exists**: register one through the signup form.

To see the dashboard with a live-looking feed and no hardware, point it at a
stand-in that serves the same JSON shape:

```bash
PLANTIQ_TS_BASE_URL=http://127.0.0.1:8731 .venv/bin/python src/wsgi.py
```

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

## Tests

`pytest -q`, 55 tests, about three seconds, **no network**.

`tests/conftest.py` has an autouse fixture that replaces `requests.get` with a
raise. Without it the dashboard fixtures really do call the public ThingSpeak
channel: the suite was nine seconds of live HTTP and would have been red on a
runner with no egress. Tests that want a feed stub the call themselves.

Every test builds its own database in a `tmp_path` through the app's own
`init_db()`. Nothing is loaded from a fixture file, which means the suite also
proves the claim in [Reference data and seeding](#reference-data-and-seeding):
that a checkout with no database becomes a working install.

| File | Covers |
|---|---|
| `test_seed.py` | A fresh database has the profiles, has no users, and re-seeding adds nothing |
| `test_auth.py` | Signup hashes, a clear-text row is re-hashed on first successful login, a wrong password re-hashes nothing, `next=` cannot leave the site |
| `test_api.py` | The device token: missing, wrong, unconfigured, header form, duplicate suppression, the legacy `/receive` path |
| `test_plants.py` | Threshold evaluation, including that a missing reading and an unusable threshold are `unknown` rather than `ok` |
| `test_sensors.py` | `"NaN"` and `Infinity` parse to `None`, field mapping, date labelling, and that a failed fetch returns an offline feed rather than raising |
| `test_views.py` | Every signed-in page renders with no telemetry at all |

The two assertions worth keeping if everything else is deleted are
`test_a_legacy_cleartext_row_is_rehashed_on_first_successful_login` and
`test_alert_ingest_rejects_everything_when_no_token_is_configured`. Both guard a
mistake this repository has already made once.

## Continuous integration

`.github/workflows/ci.yml`, three jobs:

- **Lint and test** on Python 3.10 and 3.12: `ruff check src tests` then `pytest`.
- **No database file is tracked.** Fails if any `.db`, `.sqlite` or `.sqlite3`
  shows up in `git ls-files`, and separately if a credential literal appears
  assigned to `ssid`, `password`, `apiKey`, `mqttPass`, `mqttUserName` or
  `ClientID` in the sketch. `.gitignore` does not protect against `git add -f`,
  and both of these have happened.
- **The light README matches its source.**

## Documentation and screenshots

`README.md` is the dark page, `README-light.md` its generated twin, built by
`scripts/build-light-readme.mjs` and checked by CI.

`docs/screenshots/{dark,light}` hold seven pages each, same filename in both
themes; `docs/screenshots/responsive/{dark,light}` hold three widths each.

They are viewport renders of a real instance, signed in through the app's own
signup form, with the feed served by a local stand-in via `PLANTIQ_TS_BASE_URL`.
Nothing points at the real ThingSpeak channel, and no real person's data appears
in any of them: the account in the screenshots was registered during the capture
run and the alerts were posted through `/api/alerts` with a throwaway token.

## Gotchas

- **ThingSpeak sends the string `"NaN"`** when a sensor did not report. `float()`
  accepts it, and a bare `NaN` is not valid JSON, so `jsonify` produces a body
  that `JSON.parse` rejects and the whole response fails. `sensors._to_float`
  filters non-finite values to `None`. Do not remove that check.
- **`input.valueAsDate` reads and writes UTC.** Setting it from a locally
  constructed midnight shifts the displayed day for anyone not on UTC. The
  History page formats a local `YYYY-MM-DD` string and assigns `.value` instead.
- **The channel's data ends 2023-11-21.** The hardware is not running, so the
  dashboard against the default channel is permanently in its stale state. That
  is the honest rendering, not a bug. Point `PLANTIQ_TS_CHANNEL` at a live
  channel, or `PLANTIQ_TS_BASE_URL` at a local stand-in, to see the other path.
- **The default ThingSpeak channel is world-readable.** `PLANTIQ_TS_READ_KEY` is
  not required for it, which is why a test that expected an offline feed with no
  key configured passed against the real API instead. Anything asserting the
  offline path has to stub the HTTP call.
- **`reading_no` is clamped on read as well as write.** An old row can hold a
  value outside the current bounds, and an unclamped one goes straight into a
  ThingSpeak `results` parameter.
- **The metric accent key is `temp`, not `temperature`** (`METRICS[0]["accent"]`),
  because it names the CSS variable `--c-temp`. The tile selector in `app.css`
  must match that string, not the metric key.
- **Alert dismissal is a POST**, not the old `GET /change_seen/<id>` link, so a
  crawler or a prefetch cannot clear someone's alerts.

---

## Contributors

| | |
|---|---|
| [Adari Dileep Kumar](https://github.com/Dileepadari) | Web application, API, firmware integration |
| [Gajawada Bharath](https://github.com/bharath-gajawada) | Sensors and circuit |
| [Chaganti Venkata Karthikeya](https://github.com/kryptonblade) | OM2M layer |
| [Sallepalle Naga Revanth Reddy](https://github.com/nagarevanth) | Firmware and data pipeline |

Built at IIIT Hyderabad under Aakashavani.
