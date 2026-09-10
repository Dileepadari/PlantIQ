"""Threshold evaluation: the judgement the whole dashboard rests on."""

from plantiq import plants, sensors


class FakePlant(dict):
    """A plants row. sqlite3.Row indexes by name, and so does a dict."""


MANGO = FakePlant(
    plant_name="Mango", VOC_min=0, VOC_max=300, temp_min=25, temp_max=35,
    humid_min=40, humid_max=80, moist_min=40, moist_max=80,
    CO2_min=400, CO2_max=800, light_intense_min=20, light_intense_max=100,
)


def status_for(rows, key):
    return next(row["status"] for row in rows if row["key"] == key)


def test_a_reading_inside_the_range_is_ok():
    rows = plants.evaluate(MANGO, {"temperature": 30})
    assert status_for(rows, "temperature") == "ok"


def test_the_bounds_themselves_count_as_ok():
    """25 and 35 are the stated safe range, so they cannot be alerts."""
    assert status_for(plants.evaluate(MANGO, {"temperature": 25}), "temperature") == "ok"
    assert status_for(plants.evaluate(MANGO, {"temperature": 35}), "temperature") == "ok"


def test_a_reading_outside_the_range_alerts():
    assert status_for(plants.evaluate(MANGO, {"temperature": 41}), "temperature") == "alert"
    assert status_for(plants.evaluate(MANGO, {"temperature": 4}), "temperature") == "alert"


def test_a_missing_reading_is_unknown_not_ok():
    """A dead sensor must never read as a healthy plant."""
    assert status_for(plants.evaluate(MANGO, {}), "temperature") == "unknown"
    assert status_for(plants.evaluate(MANGO, {"temperature": None}), "temperature") == "unknown"


def test_an_unusable_threshold_is_unknown_not_ok():
    """The exact bug in the shipped data: VOC_min was a single space."""
    blank = FakePlant(MANGO, VOC_min=" ")
    assert status_for(plants.evaluate(blank, {"voc": 50}), "voc") == "unknown"


def test_no_plant_selected_evaluates_everything_as_unknown():
    rows = plants.evaluate(None, {"temperature": 30})
    assert {row["status"] for row in rows} == {"unknown"}


def test_one_alert_makes_the_whole_summary_an_alert():
    rows = plants.evaluate(MANGO, {"temperature": 30, "humidity": 5})
    assert plants.health_summary(rows)["overall"] == "alert"


def test_a_summary_with_nothing_known_is_unknown_not_ok():
    assert plants.health_summary(plants.evaluate(MANGO, {}))["overall"] == "unknown"


def test_every_metric_is_reported_even_when_it_has_no_threshold():
    """The dashboard renders one card per metric, so the list length is fixed."""
    assert len(plants.evaluate(MANGO, {})) == len(sensors.METRICS)
