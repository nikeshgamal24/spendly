import uuid
import pytest
from database.queries import (
    get_recent_transactions,
    get_summary_stats,
    get_category_breakdown,
)
from database.db import get_db, create_user

DEMO_EMAIL    = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

# Seed range 2026-05-01 to 2026-05-10 covers 4 expenses:
#   Food 42.50 (May 1), Transport 15.00 (May 5),
#   Bills 120.00 (May 7), Health 30.00 (May 10)
# Total: 207.50 | Top category: Bills
FILTER_FROM = "2026-05-01"
FILTER_TO   = "2026-05-10"
FILTERED_TOTAL = "₹207.50"
UNFILTERED_TOTAL = "₹372.24"


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
    return create_user("New User", unique_email, "password123")


# ------------------------------------------------------------------ #
# get_recent_transactions — unit tests                               #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_filtered_returns_correct_count(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert len(txs) == 4


def test_get_recent_transactions_filtered_newest_first(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert txs[0]["date"] == "10 May 2026"   # newest in range
    assert txs[-1]["date"] == "01 May 2026"  # oldest in range


def test_get_recent_transactions_filter_full_month_no_limit(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id, date_from="2026-05-01", date_to="2026-05-31")
    assert len(txs) == 8


def test_get_recent_transactions_filter_out_of_range_empty(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id, date_from="2025-01-01", date_to="2025-12-31")
    assert txs == []


def test_get_recent_transactions_no_filter_applies_limit(app):
    with app.app_context():
        user_id = get_demo_user_id()
        txs = get_recent_transactions(user_id, limit=3)
    assert len(txs) == 3


# ------------------------------------------------------------------ #
# get_summary_stats — unit tests                                     #
# ------------------------------------------------------------------ #

def test_get_summary_stats_filtered(app):
    with app.app_context():
        user_id = get_demo_user_id()
        stats = get_summary_stats(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert stats["transaction_count"] == 4
    assert stats["total_spent"] == FILTERED_TOTAL
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_filter_no_results(app):
    with app.app_context():
        user_id = get_demo_user_id()
        stats = get_summary_stats(user_id, date_from="2025-01-01", date_to="2025-12-31")
    assert stats == {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}


# ------------------------------------------------------------------ #
# get_category_breakdown — unit tests                                #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_filtered_count(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert len(cats) == 4


def test_get_category_breakdown_filtered_top_category(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert cats[0]["name"] == "Bills"


def test_get_category_breakdown_filtered_pct_sums_to_100(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id, date_from=FILTER_FROM, date_to=FILTER_TO)
    assert sum(c["pct"] for c in cats) == 100


def test_get_category_breakdown_filter_no_results(app):
    with app.app_context():
        user_id = get_demo_user_id()
        cats = get_category_breakdown(user_id, date_from="2025-01-01", date_to="2025-12-31")
    assert cats == []


# ------------------------------------------------------------------ #
# GET /profile — route tests                                         #
# ------------------------------------------------------------------ #

def test_profile_filter_returns_200(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert resp.status_code == 200


def test_profile_filter_shows_filtered_total(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert b"207.50" in resp.data


def test_profile_filter_hides_unfiltered_total(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert b"372.24" not in resp.data


def test_profile_filter_prefills_from_input(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert f'value="{FILTER_FROM}"'.encode() in resp.data


def test_profile_filter_prefills_to_input(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert f'value="{FILTER_TO}"'.encode() in resp.data


def test_profile_invalid_range_returns_400(client):
    login(client)
    resp = client.get("/profile?from=2026-05-31&to=2026-05-01")
    assert resp.status_code == 400


def test_profile_only_from_param_shows_full_data(client):
    login(client)
    resp = client.get(f"/profile?from={FILTER_FROM}")
    assert resp.status_code == 200
    assert b"372.24" in resp.data


def test_profile_only_to_param_shows_full_data(client):
    login(client)
    resp = client.get(f"/profile?to={FILTER_TO}")
    assert resp.status_code == 200
    assert b"372.24" in resp.data


def test_profile_empty_user_with_filter_no_errors(client, app):
    with app.app_context():
        empty_id = create_empty_user()
        conn = get_db()
        row = conn.execute("SELECT email FROM users WHERE id = ?", (empty_id,)).fetchone()
        empty_email = row["email"]
        conn.close()

    client.post("/login", data={"email": empty_email, "password": "password123"})
    resp = client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
    assert resp.status_code == 200
    assert "₹0.00".encode() in resp.data


def test_profile_no_filter_shows_full_data(client):
    login(client)
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"372.24" in resp.data
    assert b"Demo User" in resp.data
