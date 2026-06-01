import uuid
import pytest
from database.queries import (
    get_user_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)
from database.db import get_db, create_user

DEMO_EMAIL    = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
DEMO_NAME     = "Demo User"

# Seed expenses sum: 42.50+15.00+120.00+30.00+18.99+65.00+25.00+55.75 = 372.24
EXPECTED_TOTAL = "₹372.24"
EXPECTED_COUNT = 8
EXPECTED_TOP   = "Bills"


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def get_demo_user_id():
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    conn.close()
    return row["id"]


def create_empty_user():
    unique_email = f"empty-{uuid.uuid4().hex[:8]}@example.com"
    user_id = create_user("New User", unique_email, "password123")
    return user_id


# ------------------------------------------------------------------ #
# get_user_by_id                                                      #
# ------------------------------------------------------------------ #

def test_get_user_by_id_returns_correct_fields(app):
    with app.app_context():
        user_id = get_demo_user_id()
        user = get_user_by_id(user_id)

    assert user is not None
    assert user["name"] == DEMO_NAME
    assert user["email"] == DEMO_EMAIL
    assert "member_since" in user
    assert "initials" in user
    assert user["initials"] == "DU"


def test_get_user_by_id_member_since_format(app):
    with app.app_context():
        user_id = get_demo_user_id()
        user = get_user_by_id(user_id)

    # Should be "Month YYYY" e.g. "June 2026"
    parts = user["member_since"].split()
    assert len(parts) == 2
    assert parts[1].isdigit()
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    assert parts[0] in months


def test_get_user_by_id_nonexistent_returns_none(app):
    with app.app_context():
        result = get_user_by_id(999999)
    assert result is None


# ------------------------------------------------------------------ #
# get_summary_stats                                                   #
# ------------------------------------------------------------------ #

def test_get_summary_stats_seed_user(app):
    with app.app_context():
        user_id = get_demo_user_id()
        stats = get_summary_stats(user_id)

    assert stats["total_spent"] == EXPECTED_TOTAL
    assert stats["transaction_count"] == EXPECTED_COUNT
    assert stats["top_category"] == EXPECTED_TOP


def test_get_summary_stats_no_expenses(app):
    with app.app_context():
        user_id = create_empty_user()
        stats = get_summary_stats(user_id)

    assert stats == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}


# ------------------------------------------------------------------ #
# get_recent_transactions                                             #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_seed_user(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id)

    assert len(txs) == EXPECTED_COUNT
    # Each dict has the required keys
    for tx in txs:
        assert "date" in tx
        assert "description" in tx
        assert "category" in tx
        assert "amount" in tx
        assert tx["amount"].startswith("₹")


def test_get_recent_transactions_newest_first(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id)

    # First transaction should be the most recent seed date: 2026-05-25
    assert txs[0]["date"] == "25 May 2026"
    # Last transaction should be oldest: 2026-05-01
    assert txs[-1]["date"] == "01 May 2026"


def test_get_recent_transactions_no_expenses(app):
    with app.app_context():
        user_id = create_empty_user()
        txs = get_recent_transactions(user_id)

    assert txs == []


# ------------------------------------------------------------------ #
# get_category_breakdown                                              #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_seed_user(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id)

    assert len(cats) == 7
    for cat in cats:
        assert "name" in cat
        assert "amount" in cat
        assert "pct" in cat
        assert cat["amount"].startswith("₹")
        assert isinstance(cat["pct"], int)


def test_get_category_breakdown_pct_sums_to_100(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id)

    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_ordered_by_amount(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id)

    # Bills (120.00) should be first
    assert cats[0]["name"] == "Bills"


def test_get_category_breakdown_no_expenses(app):
    with app.app_context():
        user_id = create_empty_user()
        cats = get_category_breakdown(user_id)

    assert cats == []


# ------------------------------------------------------------------ #
# GET /profile route                                                  #
# ------------------------------------------------------------------ #

def test_profile_redirects_when_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_returns_200_when_authenticated(client):
    login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200


def test_profile_shows_real_user_name(client):
    login(client)
    resp = client.get("/profile")
    assert b"Demo User" in resp.data


def test_profile_shows_real_email(client):
    login(client)
    resp = client.get("/profile")
    assert b"demo@spendly.com" in resp.data


def test_profile_shows_rupee_symbol(client):
    login(client)
    resp = client.get("/profile")
    assert "₹".encode() in resp.data


def test_profile_total_spent(client):
    login(client)
    resp = client.get("/profile")
    assert b"372.24" in resp.data


def test_profile_top_category(client):
    login(client)
    resp = client.get("/profile")
    assert b"Bills" in resp.data


def test_profile_does_not_show_hardcoded_name(client):
    login(client)
    resp = client.get("/profile")
    assert b"Priya Sharma" not in resp.data
