from database.db import get_user_by_id, find_user_by_email


DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Login success
# ---------------------------------------------------------------------------

def test_login_correct_credentials(client):
    with client:
        resp = login(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        # Re-fetch with session context
        with client.session_transaction() as sess:
            assert "user_id" in sess
            assert "user_name" in sess


# ---------------------------------------------------------------------------
# Login failures
# ---------------------------------------------------------------------------

def test_login_wrong_password(client):
    resp = login(client, password="wrongpassword")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    assert DEMO_EMAIL.encode() in resp.data


def test_login_unknown_email(client):
    resp = login(client, email="nobody@example.com")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data


def test_login_blank_email(client):
    resp = login(client, email="")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data


def test_login_blank_password(client):
    resp = login(client, password="")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data


def test_login_all_blank(client):
    resp = login(client, email="", password="")
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_clears_session(client):
    with client:
        login(client)
        resp = client.get("/logout", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")
        with client.session_transaction() as sess:
            assert "user_id" not in sess


# ---------------------------------------------------------------------------
# Nav state
# ---------------------------------------------------------------------------

def test_nav_logged_out(client):
    resp = client.get("/")
    assert b"Sign in" in resp.data
    assert b"Get started" in resp.data


def test_nav_logged_in(client):
    with client:
        login(client)
        resp = client.get("/")
        assert b"Profile" in resp.data
        assert b"Sign out" in resp.data


# ---------------------------------------------------------------------------
# Redirect when already logged in
# ---------------------------------------------------------------------------

def test_login_page_redirects_when_logged_in(client):
    with client:
        login(client)
        resp = client.get("/login", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")


def test_register_page_redirects_when_logged_in(client):
    with client:
        login(client)
        resp = client.get("/register", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")


# ---------------------------------------------------------------------------
# DB helper: get_user_by_id
# ---------------------------------------------------------------------------

def test_get_user_by_id_exists(app):
    with app.app_context():
        user = find_user_by_email(DEMO_EMAIL)
        assert user is not None
        result = get_user_by_id(user["id"])
        assert result is not None
        assert result["email"] == DEMO_EMAIL


def test_get_user_by_id_missing(app):
    with app.app_context():
        result = get_user_by_id(99999)
        assert result is None
