"""Parsing what ThingSpeak actually sends, including the parts that are not numbers."""

from datetime import datetime, timedelta

from plantiq import sensors


def test_a_missing_sensor_reads_as_no_reading():
    """ThingSpeak writes the string "NaN" when a sensor did not report.

    float() accepts that happily, and a bare NaN is not valid JSON, so leaving
    it through breaks every API response that carries it.
    """
    assert sensors._to_float("NaN") is None
    assert sensors._to_float("Infinity") is None
    assert sensors._to_float(None) is None
    assert sensors._to_float("") is None
    assert sensors._to_float("not a number") is None


def test_real_values_survive_and_are_rounded():
    assert sensors._to_float("27.456") == 27.46
    assert sensors._to_float(0) == 0.0


def test_fields_are_mapped_to_names():
    reading = sensors._parse_feed(
        {
            "created_at": "2026-09-10T08:30:00+05:30",
            "field1": "27", "field2": "55", "field3": "80",
            "field4": "120", "field5": "500", "field6": "60",
        }
    )
    assert reading["temperature"] == 27
    assert reading["humidity"] == 60
    assert reading["moisture"] == 55
    assert reading["co2"] == 500


def test_an_old_reading_is_labelled_with_its_date():
    """Without the date, an archived channel looks live, which is the one thing
    a monitoring dashboard must never imply."""
    old = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    label = sensors._short_time(old)
    assert len(label) > 5 and ":" in label


def test_a_reading_from_today_is_labelled_with_the_time_alone():
    today = datetime.now().replace(hour=9, minute=5).strftime("%Y-%m-%dT%H:%M:%S")
    assert sensors._short_time(today) == "09:05"


def test_an_unparseable_timestamp_does_not_raise():
    assert sensors._short_time("whenever") == "whenever"
    assert sensors._short_time(None) == ""


def test_a_failed_fetch_returns_an_empty_offline_feed_rather_than_raising(app, monkeypatch):
    """A monitoring page that 500s because the API is slow is worse than one
    that says "offline", so fetch_readings swallows the exception."""

    def explode(*args, **kwargs):
        raise sensors.requests.Timeout("simulated")

    monkeypatch.setattr(sensors.requests, "get", explode)
    with app.app_context():
        feed = sensors.fetch_readings(5)
    assert feed["online"] is False
    assert feed["readings"] == []
    assert feed["latest"] is None


def test_a_successful_fetch_is_oldest_first_so_charts_plot_it_directly(app, monkeypatch):
    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "feeds": [
                    {"created_at": "2026-09-10T08:00:00+05:30", "field1": "20"},
                    {"created_at": "2026-09-10T09:00:00+05:30", "field1": "30"},
                ]
            }

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(sensors.requests, "get", lambda *a, **k: Response())
    with app.app_context():
        feed = sensors.fetch_readings(2)
    assert feed["online"] is True
    assert [r["temperature"] for r in feed["readings"]] == [20, 30]
    assert feed["latest"]["temperature"] == 30
