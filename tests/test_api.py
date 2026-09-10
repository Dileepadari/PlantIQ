"""The device-facing endpoint.

/api/alerts is the only route a machine on the internet can reach without a
session, so its token check is the boundary worth testing hardest.
"""

from conftest import DEVICE_TOKEN


def test_alert_ingest_rejects_a_missing_token(client):
    response = client.post("/api/alerts", json={"plant_name": "Mango", "msg": "dry"})
    assert response.status_code == 401


def test_alert_ingest_rejects_a_wrong_token(client):
    response = client.post(
        "/api/alerts",
        json={"secret": "not-the-token", "plant_name": "Mango", "msg": "dry"},
    )
    assert response.status_code == 401


def test_alert_ingest_rejects_everything_when_no_token_is_configured(app, client):
    """An unset DEVICE_TOKEN must close the endpoint, not open it."""
    app.config["DEVICE_TOKEN"] = ""
    for payload in ({"secret": "", "plant_name": "Mango", "msg": "dry"},
                    {"plant_name": "Mango", "msg": "dry"}):
        assert client.post("/api/alerts", json=payload).status_code == 401


def test_alert_ingest_accepts_the_configured_token(client):
    response = client.post(
        "/api/alerts",
        json={"secret": DEVICE_TOKEN, "plant_name": "Mango", "msg": "Soil is dry"},
    )
    assert response.status_code == 201


def test_the_token_may_also_arrive_as_a_header(client):
    response = client.post(
        "/api/alerts",
        json={"plant_name": "Mango", "msg": "Header route"},
        headers={"X-Device-Token": DEVICE_TOKEN},
    )
    assert response.status_code == 201


def test_alert_ingest_requires_a_plant_and_a_message(client):
    for payload in ({"secret": DEVICE_TOKEN, "msg": "no plant"},
                    {"secret": DEVICE_TOKEN, "plant_name": "Mango"},
                    {"secret": DEVICE_TOKEN, "plant_name": " ", "msg": " "}):
        assert client.post("/api/alerts", json=payload).status_code == 400


def test_an_unknown_alert_type_becomes_a_warning_rather_than_being_rejected(client, signed_in):
    client.post(
        "/api/alerts",
        json={
            "secret": DEVICE_TOKEN,
            "plant_name": "Mango",
            "msg": "Odd type",
            "notif_type": "catastrophe",
        },
    )
    alerts = signed_in.get("/api/alerts").get_json()["alerts"]
    assert [a["type"] for a in alerts if a["message"] == "Odd type"] == ["warning"]


def test_the_same_pending_alert_is_not_recorded_twice(client):
    body = {"secret": DEVICE_TOKEN, "plant_name": "Mango", "msg": "Repeated"}
    assert client.post("/api/alerts", json=body).status_code == 201
    second = client.post("/api/alerts", json=body)
    assert second.status_code == 200
    assert second.get_json()["status"] == "duplicate"


def test_the_legacy_receive_path_still_works(client):
    """Firmware already in the field posts to /receive, not /api/alerts."""
    response = client.post(
        "/receive",
        json={"secret": DEVICE_TOKEN, "plant_name": "Mango", "msg": "Legacy path"},
    )
    assert response.status_code == 201


def test_api_reads_need_a_session(client):
    for path in ("/api/readings", "/api/history", "/api/alerts"):
        assert client.get(path).status_code == 302, path
