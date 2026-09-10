"""Every signed-in page renders, including when the sensor channel is down."""

import pytest

PAGES = ["/", "/statistics", "/analysis", "/history", "/alerts", "/circuit", "/about", "/settings"]


@pytest.mark.parametrize("path", PAGES)
def test_a_page_renders_with_no_telemetry_at_all(signed_in, path):
    """The `no_network` fixture is active, so this is the offline path: a
    monitoring dashboard has to stay readable when the device is unreachable."""
    assert signed_in.get(path).status_code == 200


def test_a_bad_url_gets_the_error_page_not_a_stack_trace(signed_in):
    response = signed_in.get("/no-such-page")
    assert response.status_code == 404
    assert b"does not exist" in response.data


def test_a_bad_api_url_gets_json_not_html(client):
    response = client.get("/api/no-such-endpoint")
    assert response.status_code == 404
    assert response.get_json()["status"] == "error"


def test_settings_can_change_the_tracked_plant(app, signed_in):
    signed_in.post(
        "/settings",
        data={"name": "Demo Grower", "plant": "Cactus", "reading": "25"},
        follow_redirects=True,
    )
    with app.app_context():
        from plantiq.db import query_one

        user = query_one("SELECT plant, reading_no FROM users WHERE username = 'demo'")
    assert user["plant"] == "Cactus"
    assert user["reading_no"] == 25


def test_settings_refuses_a_readings_count_outside_the_bounds(app, signed_in):
    """Signup clamps this value; settings rejects it. Both are defensible, and
    the difference is deliberate here only in the sense that it is tested."""
    response = signed_in.post(
        "/settings",
        data={"name": "Demo Grower", "plant": "Mango", "reading": "99999"},
    )
    assert b"between" in response.data
    with app.app_context():
        from plantiq.db import query_one

        stored = query_one("SELECT reading_no FROM users WHERE username = 'demo'")["reading_no"]
    assert stored == 20


def test_settings_refuses_a_plant_that_is_not_in_the_database(signed_in):
    response = signed_in.post(
        "/settings",
        data={"name": "Demo Grower", "plant": "Triffid", "reading": "20"},
    )
    assert b"not in the plant database" in response.data


def test_dismissing_an_alert_removes_it_from_the_unread_list(client, signed_in):
    from conftest import DEVICE_TOKEN

    client.post("/api/alerts",
                json={"secret": DEVICE_TOKEN, "plant_name": "Mango", "msg": "Dismiss me"})
    alerts = signed_in.get("/api/alerts").get_json()["alerts"]
    target = next(a for a in alerts if a["message"] == "Dismiss me")

    signed_in.post(f"/alerts/{target['id']}/dismiss", follow_redirects=True)

    remaining = signed_in.get("/api/alerts").get_json()["alerts"]
    assert all(a["message"] != "Dismiss me" for a in remaining)
