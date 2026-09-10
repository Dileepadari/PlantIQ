"""Test fixtures.

Every test gets its own empty database file, built by the app's own
``init_db()`` rather than by a checked-in fixture, so the tests also prove that
a fresh checkout with no database becomes a working install.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from plantiq import create_app  # noqa: E402
from plantiq.config import Config  # noqa: E402

DEMO_PASSWORD = "greenhouse123"
DEVICE_TOKEN = "test-device-token"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nothing in the suite is allowed to reach ThingSpeak.

    Without this the dashboard fixtures really do call the public channel: the
    suite was nine seconds of network and would have been red on a runner with
    no egress. Tests that want a feed stub `requests.get` themselves.
    """
    from plantiq import sensors

    def refuse(*args, **kwargs):
        raise sensors.requests.ConnectionError("network disabled in tests")

    monkeypatch.setattr(sensors.requests, "get", refuse)
    sensors._cache.clear()


@pytest.fixture
def app(tmp_path):
    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = "test-only"
        DATABASE = str(tmp_path / "test.db")
        DEVICE_TOKEN = DEVICE_TOKEN
        # No network in tests. Every ThingSpeak call is stubbed or expected to
        # fail closed, and a zero TTL stops one test's cache reaching the next.
        THINGSPEAK_READ_KEY = ""
        THINGSPEAK_CACHE_TTL = 0

    return create_app(TestConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def signed_in(app, client):
    """A client that registered through the app's own signup form."""
    client.post(
        "/signup",
        data={
            "username": "demo",
            "email": "demo@example.com",
            "password": DEMO_PASSWORD,
            "name": "Demo Grower",
            "plant": "Mango",
            "init_read": "20",
        },
        follow_redirects=True,
    )
    return client
