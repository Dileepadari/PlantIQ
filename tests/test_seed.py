"""A checkout with no database file has to become a working install."""

from plantiq.db import load_plants, query_all, seed_plants


def test_a_fresh_database_carries_the_plant_profiles(app):
    with app.app_context():
        names = [row["plant_name"] for row in query_all("SELECT plant_name FROM plants")]
    assert sorted(names) == sorted(plant["plant_name"] for plant in load_plants())


def test_no_users_are_seeded(app):
    """The old database shipped real accounts. Nothing ships accounts now."""
    with app.app_context():
        assert query_all("SELECT * FROM users") == []


def test_seeding_twice_adds_nothing(app):
    with app.app_context():
        assert seed_plants() == 0


def test_every_plant_has_a_usable_voc_range(app):
    """Rose carried a single space in VOC_min, which silently disabled its VOC
    alerting: _to_float returned None and thresholds_for skipped the metric."""
    for plant in load_plants():
        assert isinstance(plant["VOC_min"], (int, float)), plant["plant_name"]
        assert isinstance(plant["VOC_max"], (int, float)), plant["plant_name"]
