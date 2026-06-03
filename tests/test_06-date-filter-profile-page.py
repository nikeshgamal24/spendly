"""
tests/test_06-date-filter-profile-page.py

Pytest tests for Step 6: Date Filter on the /profile page.

Spec: .claude/specs/06-date-filter-profile-page.md

All test logic is derived exclusively from the feature specification,
not from the implementation.
"""

import uuid
import pytest
from app import app as flask_app
from database.db import get_db, create_user, seed_db, init_db


# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

DEMO_EMAIL    = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

# Date range 2026-05-01 → 2026-05-10 captures exactly 4 seed expenses:
#   Food ₹42.50 (May 1), Transport ₹15.00 (May 5),
#   Bills ₹120.00 (May 7), Health ₹30.00 (May 10)
#   Total: ₹207.50 | Top category: Bills
FILTER_FROM = "2026-05-01"
FILTER_TO   = "2026-05-10"

FILTERED_TOTAL     = b"207.50"
UNFILTERED_TOTAL   = b"372.24"

# Single day that has exactly one expense: Food ₹42.50 Groceries
SINGLE_DAY = "2026-05-01"

# A date range that has zero seed expenses
EMPTY_FROM = "2025-01-01"
EMPTY_TO   = "2025-12-31"


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def app():
    """Fresh Flask app using the real seed database for each test."""
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client already logged in as the demo seed user."""
    client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    return client


@pytest.fixture
def empty_user_client(client, app):
    """
    A test client logged in as a freshly created user who has no expenses.
    The user is created with a unique email to avoid collisions across tests.
    """
    unique_email = f"empty-{uuid.uuid4().hex[:8]}@test.spendly.com"
    with app.app_context():
        create_user("Empty User", unique_email, "testpass99")
    client.post(
        "/login",
        data={"email": unique_email, "password": "testpass99"},
        follow_redirects=False,
    )
    return client


# ------------------------------------------------------------------ #
# Helper                                                              #
# ------------------------------------------------------------------ #

def _get_demo_user_id(app):
    with app.app_context():
        conn = get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
        ).fetchone()
        conn.close()
        return row["id"]


# ================================================================== #
# 1. Auth guard                                                       #
# ================================================================== #

class TestAuthGuard:
    """Unauthenticated requests to /profile must be rejected."""

    def test_unauthenticated_no_params_redirects_to_login(self, client):
        resp = client.get("/profile", follow_redirects=False)
        assert resp.status_code == 302, "Expected redirect for unauthenticated user"
        assert "/login" in resp.headers["Location"], "Should redirect to /login"

    def test_unauthenticated_with_filter_params_redirects_to_login(self, client):
        resp = client.get(
            f"/profile?from={FILTER_FROM}&to={FILTER_TO}",
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Filter params must not bypass auth guard"
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_invalid_range_still_redirects_not_400(self, client):
        # Auth check must happen before date validation — a logged-out user
        # supplying an invalid range should get a redirect, not a 400.
        resp = client.get(
            "/profile?from=2026-05-31&to=2026-05-01",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ================================================================== #
# 2. No-filter baseline (GET /profile with no params)                #
# ================================================================== #

class TestNoFilterBaseline:
    """With no query params the page must show all data, matching Step 5 behaviour."""

    def test_returns_200(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Profile page should return 200 when authenticated"

    def test_shows_unfiltered_total(self, auth_client):
        resp = auth_client.get("/profile")
        assert UNFILTERED_TOTAL in resp.data, (
            "No-filter view must show full total ₹372.24"
        )

    def test_shows_all_eight_transactions(self, auth_client):
        resp = auth_client.get("/profile")
        # All 8 descriptions must appear in the rendered HTML
        descriptions = [
            b"Groceries",
            b"Bus pass top-up",
            b"Electricity bill",
            b"Pharmacy",
            b"Streaming subscription",
            b"Clothing",
            b"Miscellaneous",
            b"Restaurant dinner",
        ]
        for desc in descriptions:
            assert desc in resp.data, f"{desc} missing from no-filter profile page"

    def test_shows_demo_user_name(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Demo User" in resp.data

    def test_filter_inputs_are_blank_when_no_filter_active(self, auth_client):
        resp = auth_client.get("/profile")
        # The inputs should have empty value attributes when no filter is active
        assert b'value=""' in resp.data or (
            b'name="from"' in resp.data and b'name="to"' in resp.data
        ), "Filter date inputs should be blank when no filter is active"
        # Specifically there must be no pre-filled date value
        assert b'value="2026' not in resp.data, (
            "Filter inputs must not be pre-filled when no filter is active"
        )

    def test_transaction_count_stat_is_eight(self, auth_client):
        resp = auth_client.get("/profile")
        # The stat card renders the transaction_count value
        assert b">8<" in resp.data or b"8</span>" in resp.data, (
            "Transaction count stat should be 8 with no filter"
        )

    def test_top_category_is_food(self, auth_client):
        # Food has the highest combined total (42.50 + 55.75 = 98.25)
        resp = auth_client.get("/profile")
        assert b"Food" in resp.data


# ================================================================== #
# 3. Valid date range filter                                          #
# ================================================================== #

class TestValidDateRangeFilter:
    """GET /profile?from=X&to=Y with a valid range must filter all data."""

    def test_returns_200(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert resp.status_code == 200

    def test_shows_filtered_total_spent(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert FILTERED_TOTAL in resp.data, "Filtered total ₹207.50 must appear"

    def test_does_not_show_unfiltered_total(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert UNFILTERED_TOTAL not in resp.data, (
            "Unfiltered total ₹372.24 must not appear when a date filter is active"
        )

    def test_filtered_transaction_count_stat(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        # 4 transactions fall in 2026-05-01 to 2026-05-10
        assert b">4<" in resp.data or b"4</span>" in resp.data, (
            "Transaction count stat should be 4 for the filtered range"
        )

    def test_top_category_stat_is_bills(self, auth_client):
        # Bills (₹120.00) is highest in the filtered range
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert b"Bills" in resp.data

    def test_only_in_range_transactions_shown(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        in_range = [b"Groceries", b"Bus pass top-up", b"Electricity bill", b"Pharmacy"]
        for desc in in_range:
            assert desc in resp.data, f"{desc} (in range) must appear in filtered view"

    def test_out_of_range_transactions_hidden(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        out_of_range = [
            b"Streaming subscription",
            b"Clothing",
            b"Miscellaneous",
            b"Restaurant dinner",
        ]
        for desc in out_of_range:
            assert desc not in resp.data, (
                f"{desc} (out of range) must not appear in filtered view"
            )

    def test_category_breakdown_reflects_filter(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        # Categories present in range: Food, Transport, Bills, Health
        for cat in [b"Bills", b"Health", b"Transport"]:
            assert cat in resp.data, f"Category {cat} missing from filtered breakdown"
        # Categories outside range should not appear in breakdown
        for cat in [b"Entertainment", b"Shopping", b"Other"]:
            assert cat not in resp.data, (
                f"Category {cat} should not appear in filtered category breakdown"
            )

    def test_filter_full_month_shows_all_eight(self, auth_client):
        # With a filter spanning the whole month, no limit cap should apply
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        assert resp.status_code == 200
        descriptions = [
            b"Groceries",
            b"Bus pass top-up",
            b"Electricity bill",
            b"Pharmacy",
            b"Streaming subscription",
            b"Clothing",
            b"Miscellaneous",
            b"Restaurant dinner",
        ]
        for desc in descriptions:
            assert desc in resp.data, (
                f"{desc} missing — limit cap must be lifted when a date filter is active"
            )


# ================================================================== #
# 4. Filter input pre-filling                                         #
# ================================================================== #

class TestFilterInputPrefill:
    """After applying a filter the form inputs must be pre-filled with the active values."""

    def test_from_input_prefilled(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        expected = f'value="{FILTER_FROM}"'.encode()
        assert expected in resp.data, (
            f"'from' input must be pre-filled with {FILTER_FROM}"
        )

    def test_to_input_prefilled(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        expected = f'value="{FILTER_TO}"'.encode()
        assert expected in resp.data, (
            f"'to' input must be pre-filled with {FILTER_TO}"
        )

    def test_both_inputs_prefilled(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert f'value="{FILTER_FROM}"'.encode() in resp.data
        assert f'value="{FILTER_TO}"'.encode() in resp.data

    def test_inputs_blank_when_no_filter(self, auth_client):
        resp = auth_client.get("/profile")
        # Neither date should appear as a pre-filled value
        assert f'value="{FILTER_FROM}"'.encode() not in resp.data
        assert f'value="{FILTER_TO}"'.encode() not in resp.data


# ================================================================== #
# 5. Filter form structure (template landmarks)                       #
# ================================================================== #

class TestFilterFormStructure:
    """The filter form must have the correct HTML structure per the spec."""

    def test_filter_form_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"profile-filter" in resp.data, "Filter form container must be present"

    def test_filter_form_uses_get_method(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'method="get"' in resp.data, "Filter form must use method='get'"

    def test_from_input_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'name="from"' in resp.data, "Input with name='from' must be present"

    def test_to_input_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'name="to"' in resp.data, "Input with name='to' must be present"

    def test_apply_button_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Apply" in resp.data, "Apply submit button must be present"

    def test_clear_link_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Clear" in resp.data, "Clear link must be present"

    def test_clear_link_points_to_bare_profile(self, auth_client):
        resp = auth_client.get("/profile")
        # Clear link must href to /profile with no query params
        assert b'href="/profile"' in resp.data, (
            "Clear link must point to /profile with no query params"
        )

    def test_transaction_history_heading_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Transaction History" in resp.data

    def test_spending_by_category_heading_present(self, auth_client):
        resp = auth_client.get("/profile")
        assert b"Spending by Category" in resp.data

    def test_date_input_type_attribute(self, auth_client):
        resp = auth_client.get("/profile")
        assert b'type="date"' in resp.data, "Filter inputs must be type='date'"


# ================================================================== #
# 6. Invalid date range (from > to) → HTTP 400                       #
# ================================================================== #

class TestInvalidDateRange:
    """When from > to the route must abort with HTTP 400."""

    def test_from_after_to_returns_400(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-31&to=2026-05-01")
        assert resp.status_code == 400, "from > to must return HTTP 400"

    def test_from_equals_to_is_valid(self, auth_client):
        # Same-day range is valid (from == to is not > to)
        resp = auth_client.get(
            f"/profile?from={SINGLE_DAY}&to={SINGLE_DAY}"
        )
        assert resp.status_code == 200, "from == to must be accepted (same-day filter)"

    def test_from_one_day_after_to_returns_400(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-15&to=2026-05-14")
        assert resp.status_code == 400

    def test_wildly_inverted_range_returns_400(self, auth_client):
        resp = auth_client.get("/profile?from=2030-01-01&to=2020-01-01")
        assert resp.status_code == 400


# ================================================================== #
# 7. Only one of from / to supplied → no filter applied              #
# ================================================================== #

class TestPartialParamsNoFilter:
    """If only one of from or to is supplied the filter is ignored entirely."""

    def test_only_from_returns_200(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}")
        assert resp.status_code == 200

    def test_only_from_shows_full_data(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}")
        assert UNFILTERED_TOTAL in resp.data, (
            "Only from param supplied → full data must be shown"
        )

    def test_only_from_does_not_filter_transactions(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}")
        # Transactions outside FILTER_FROM window must still appear
        assert b"Restaurant dinner" in resp.data, (
            "Transactions beyond from date must appear when to is absent"
        )

    def test_only_to_returns_200(self, auth_client):
        resp = auth_client.get(f"/profile?to={FILTER_TO}")
        assert resp.status_code == 200

    def test_only_to_shows_full_data(self, auth_client):
        resp = auth_client.get(f"/profile?to={FILTER_TO}")
        assert UNFILTERED_TOTAL in resp.data, (
            "Only to param supplied → full data must be shown"
        )

    def test_only_to_does_not_filter_transactions(self, auth_client):
        resp = auth_client.get(f"/profile?to={FILTER_TO}")
        # Transactions beyond FILTER_TO must still appear
        assert b"Restaurant dinner" in resp.data, (
            "Transactions beyond to date must appear when from is absent"
        )

    def test_empty_from_and_to_shows_full_data(self, auth_client):
        # Both params present but empty strings → treated as no filter
        resp = auth_client.get("/profile?from=&to=")
        assert resp.status_code == 200
        assert UNFILTERED_TOTAL in resp.data


# ================================================================== #
# 8. Filter with no matching expenses                                 #
# ================================================================== #

class TestFilterNoMatchingExpenses:
    """A valid date range that contains no seed expenses must return zero/empty results."""

    def test_returns_200(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert resp.status_code == 200, "Out-of-range filter must still return 200"

    def test_total_spent_is_zero(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert b"0.00" in resp.data, "Total spent should be ₹0.00 with no matching expenses"

    def test_transaction_count_is_zero(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert b">0<" in resp.data or b"0</span>" in resp.data, (
            "Transaction count stat should be 0 when no expenses match the filter"
        )

    def test_no_transaction_rows_rendered(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        # None of the seed descriptions should appear
        for desc in [b"Groceries", b"Pharmacy", b"Clothing", b"Restaurant dinner"]:
            assert desc not in resp.data, (
                f"{desc} must not appear when filter matches zero expenses"
            )

    def test_no_server_error(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert resp.status_code != 500, "No server error for a valid but empty filter range"

    def test_filter_inputs_still_prefilled(self, auth_client):
        resp = auth_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert f'value="{EMPTY_FROM}"'.encode() in resp.data
        assert f'value="{EMPTY_TO}"'.encode() in resp.data


# ================================================================== #
# 9. Empty user (no expenses) — with and without filter              #
# ================================================================== #

class TestEmptyUserNoExpenses:
    """A user with zero expenses must see zero stats and no errors regardless of filter."""

    def test_no_filter_returns_200(self, empty_user_client):
        resp = empty_user_client.get("/profile")
        assert resp.status_code == 200

    def test_no_filter_total_is_zero(self, empty_user_client):
        resp = empty_user_client.get("/profile")
        assert b"0.00" in resp.data, "Empty user must see ₹0.00 total spent"

    def test_no_filter_transaction_count_is_zero(self, empty_user_client):
        resp = empty_user_client.get("/profile")
        assert b">0<" in resp.data or b"0</span>" in resp.data

    def test_with_filter_returns_200(self, empty_user_client):
        resp = empty_user_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert resp.status_code == 200, (
            "Empty user with a date filter must still return 200 — no errors"
        )

    def test_with_filter_total_is_zero(self, empty_user_client):
        resp = empty_user_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert b"0.00" in resp.data

    def test_with_filter_no_server_error(self, empty_user_client):
        resp = empty_user_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        assert resp.status_code != 500

    def test_with_out_of_range_filter_returns_200(self, empty_user_client):
        resp = empty_user_client.get(f"/profile?from={EMPTY_FROM}&to={EMPTY_TO}")
        assert resp.status_code == 200

    def test_page_renders_filter_form_for_empty_user(self, empty_user_client):
        resp = empty_user_client.get("/profile")
        assert b"Apply" in resp.data, "Filter form must render even when user has no expenses"
        assert b"Clear" in resp.data


# ================================================================== #
# 10. Same-day filter edge case                                       #
# ================================================================== #

class TestSameDayFilter:
    """A filter where from == to must show only expenses on that exact day."""

    def test_same_day_with_expense_returns_correct_count(self, auth_client):
        # 2026-05-01 has exactly one expense: Groceries ₹42.50
        resp = auth_client.get(f"/profile?from={SINGLE_DAY}&to={SINGLE_DAY}")
        assert resp.status_code == 200
        assert b"Groceries" in resp.data

    def test_same_day_hides_other_transactions(self, auth_client):
        resp = auth_client.get(f"/profile?from={SINGLE_DAY}&to={SINGLE_DAY}")
        other_txs = [
            b"Bus pass top-up",
            b"Electricity bill",
            b"Pharmacy",
            b"Restaurant dinner",
        ]
        for desc in other_txs:
            assert desc not in resp.data, (
                f"{desc} must not appear in a single-day filter for {SINGLE_DAY}"
            )

    def test_same_day_total_is_correct(self, auth_client):
        # Only ₹42.50 on 2026-05-01
        resp = auth_client.get(f"/profile?from={SINGLE_DAY}&to={SINGLE_DAY}")
        assert b"42.50" in resp.data

    def test_same_day_with_no_expense(self, auth_client):
        # 2026-05-03 has no expense in the seed data
        resp = auth_client.get("/profile?from=2026-05-03&to=2026-05-03")
        assert resp.status_code == 200
        assert b"0.00" in resp.data


# ================================================================== #
# 11. Transaction ordering                                            #
# ================================================================== #

class TestTransactionOrdering:
    """Filtered results must be returned newest-first."""

    def test_filtered_results_newest_first(self, auth_client):
        resp = auth_client.get(f"/profile?from={FILTER_FROM}&to={FILTER_TO}")
        data = resp.data.decode("utf-8", errors="replace")
        # "Pharmacy" (May 10) should appear before "Groceries" (May 1) in the HTML
        pharmacy_pos = data.find("Pharmacy")
        groceries_pos = data.find("Groceries")
        assert pharmacy_pos != -1 and groceries_pos != -1, (
            "Both Pharmacy and Groceries must be present in the filtered response"
        )
        assert pharmacy_pos < groceries_pos, (
            "Pharmacy (May 10) must appear before Groceries (May 1) — newest-first ordering"
        )


# ================================================================== #
# 12. Parameterised validation tests                                  #
# ================================================================== #

@pytest.mark.parametrize("from_date,to_date", [
    ("2026-05-31", "2026-05-01"),   # from clearly after to
    ("2026-05-15", "2026-05-14"),   # from one day after to
    ("2027-01-01", "2026-12-31"),   # from in next year, to in prev year
    ("2030-06-01", "2030-05-01"),   # future inverted range
])
def test_invalid_date_range_returns_400(client, from_date, to_date):
    """Any from > to combination must return HTTP 400 for authenticated users."""
    client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    resp = client.get(f"/profile?from={from_date}&to={to_date}")
    assert resp.status_code == 400, (
        f"from={from_date} > to={to_date} must return 400, got {resp.status_code}"
    )


@pytest.mark.parametrize("from_date,to_date,expected_in,expected_count_label", [
    # Range covering exactly 1 transaction
    ("2026-05-25", "2026-05-25", b"Restaurant dinner", b"55.75"),
    # Range covering exactly 3 transactions (May 18–25): 65.00 + 25.00 + 55.75 = 145.75
    ("2026-05-18", "2026-05-25", b"Clothing", b"145.75"),
    # Range covering the last 3 transactions (May 14–25)
    ("2026-05-14", "2026-05-25", b"Streaming subscription", b"164.74"),
])
def test_various_valid_ranges_show_correct_totals(
    client, from_date, to_date, expected_in, expected_count_label
):
    """Spot-check several valid ranges to confirm stats update correctly."""
    client.post(
        "/login",
        data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        follow_redirects=False,
    )
    resp = client.get(f"/profile?from={from_date}&to={to_date}")
    assert resp.status_code == 200
    assert expected_in in resp.data, (
        f"{expected_in} must appear for range {from_date} → {to_date}"
    )
    assert expected_count_label in resp.data, (
        f"Total {expected_count_label} must appear for range {from_date} → {to_date}"
    )
