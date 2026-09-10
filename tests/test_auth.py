"""Sign-up, sign-in, and the clear-text migration path.

The migration test is the one that matters. This repository published six real
accounts with clear-text passwords, and the fix is only half done if a surviving
clear-text row never becomes a hash.
"""

from conftest import DEMO_PASSWORD

from plantiq.db import query_one
from plantiq.security import hash_password, is_hashed, verify_password


def test_signup_stores_a_hash_not_the_password(app, client):
    client.post(
        "/signup",
        data={
            "username": "grower",
            "email": "grower@example.com",
            "password": DEMO_PASSWORD,
            "name": "Grower",
            "plant": "Mango",
        },
        follow_redirects=True,
    )
    with app.app_context():
        stored = query_one("SELECT password FROM users WHERE username = 'grower'")["password"]
    assert stored != DEMO_PASSWORD
    assert is_hashed(stored)


def test_a_legacy_cleartext_row_is_rehashed_on_first_successful_login(app, client):
    """The exact shape of every row that was published."""
    with app.app_context():
        from plantiq.db import execute

        execute(
            "INSERT INTO users (username, email, password, Name, plant) "
            "VALUES (?, ?, ?, ?, ?)",
            ("legacy", "legacy@example.com", "Legacyname", "Legacy Person", "Mango"),
        )

    response = client.post(
        "/login", data={"username": "legacy", "password": "Legacyname"}
    )
    assert response.status_code == 302

    with app.app_context():
        stored = query_one("SELECT password FROM users WHERE username = 'legacy'")["password"]
    assert is_hashed(stored)
    assert verify_password(stored, "Legacyname")


def test_a_wrong_password_does_not_rehash_anything(app, client):
    with app.app_context():
        from plantiq.db import execute

        execute(
            "INSERT INTO users (username, email, password, Name, plant) "
            "VALUES (?, ?, ?, ?, ?)",
            ("legacy2", "legacy2@example.com", "Secretword", "Legacy Two", "Mango"),
        )

    client.post("/login", data={"username": "legacy2", "password": "wrong"})

    with app.app_context():
        stored = query_one("SELECT password FROM users WHERE username = 'legacy2'")["password"]
    assert stored == "Secretword"


def test_login_accepts_either_username_or_email(signed_in):
    signed_in.get("/logout")
    by_email = signed_in.post(
        "/login", data={"username": "demo@example.com", "password": DEMO_PASSWORD}
    )
    assert by_email.status_code == 302


def test_signup_refuses_a_duplicate_email(app, client, signed_in):
    signed_in.get("/logout")
    response = client.post(
        "/signup",
        data={
            "username": "another",
            "email": "demo@example.com",
            "password": DEMO_PASSWORD,
            "name": "Another",
        },
    )
    assert b"already exists" in response.data


def test_signup_refuses_a_short_password(client):
    response = client.post(
        "/signup",
        data={
            "username": "short",
            "email": "short@example.com",
            "password": "abc",
            "name": "Short",
        },
    )
    assert b"at least 6 characters" in response.data


def test_signup_refuses_a_malformed_email(client):
    response = client.post(
        "/signup",
        data={
            "username": "bad",
            "email": "not-an-email",
            "password": DEMO_PASSWORD,
            "name": "Bad",
        },
    )
    assert b"email address" in response.data


def test_signed_out_pages_redirect_to_login(client):
    for path in ("/", "/history", "/analysis", "/settings", "/alerts"):
        response = client.get(path)
        assert response.status_code == 302, path
        assert "/login" in response.headers["Location"], path


def test_login_only_redirects_to_a_relative_path(client, signed_in):
    """`next` is attacker-controllable, so an absolute URL must be ignored."""
    signed_in.get("/logout")
    response = signed_in.post(
        "/login?next=https://example.com/phish",
        data={"username": "demo", "password": DEMO_PASSWORD},
    )
    assert "example.com" not in response.headers["Location"]


def test_hashing_the_same_password_twice_gives_different_hashes(app):
    assert hash_password("same") != hash_password("same")
