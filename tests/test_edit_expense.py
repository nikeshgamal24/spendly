"""
tests/test_edit_expense.py
Tests for the Edit Expense feature (Step 8).

Spec: .claude/specs/08-edit-expense.md
Routes under test:
  GET  /expenses/<int:id>/edit
  POST /expenses/<int:id>/edit
"""

import uuid
import pytest
from database.db import get_db, create_user
from database.queries import get_expense_by_id, update_expense, CATEGORIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

VALID_AMOUNT = "75.0"
VALID_CATEGORY = "Food"
VALID_DATE = "2026-04-10"
VALID_DESCRIPTION = "Updated lunch"


def _get_demo_user_id():
    """Return the id of the seeded demo user."""
    conn = get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    conn.close()
    return row["id"]


def _create_expense(user_id, amount=50.0, category="Food",
                    date="2026-03-15", description="Test expense"):
    """Insert a test expense directly into the DB and return its id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def _create_other_user():
    """Create a distinct user with a unique email and return their id."""
    unique_email = f"other-{uuid.uuid4().hex[:8]}@example.com"
    return create_user("Other User", unique_email, "otherpass123")


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def _set_session_user(client, user_id):
    """Directly inject user_id into the Flask session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _fetch_expense_row(expense_id):
    """Read raw expense row from DB for assertion on DB side effects."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# Auth guard — GET
# ---------------------------------------------------------------------------

class TestAuthGuardGet:
    def test_get_edit_logged_out_redirects_to_login(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=False)
        assert resp.status_code == 302, "Expected redirect for unauthenticated GET"
        assert "/login" in resp.headers["Location"], (
            "Unauthenticated GET should redirect to /login"
        )

    def test_get_edit_logged_out_does_not_expose_form(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/edit", follow_redirects=True)
        assert b"<form" not in resp.data or b"login" in resp.data.lower(), (
            "Unauthenticated request must not render the edit form"
        )


# ---------------------------------------------------------------------------
# Auth guard — POST
# ---------------------------------------------------------------------------

class TestAuthGuardPost:
    def test_post_edit_logged_out_redirects_to_login(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Expected redirect for unauthenticated POST"
        assert "/login" in resp.headers["Location"], (
            "Unauthenticated POST should redirect to /login"
        )

    def test_post_edit_logged_out_does_not_modify_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=50.0)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "9999.0",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "Should not persist",
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["amount"] == 50.0, "Unauthenticated POST must not modify the DB"


# ---------------------------------------------------------------------------
# Ownership / 404
# ---------------------------------------------------------------------------

class TestOwnershipAnd404:
    def test_get_nonexistent_expense_returns_404(self, client, app):
        with app.app_context():
            _set_session_user(client, _get_demo_user_id())

        resp = client.get("/expenses/999999/edit")
        assert resp.status_code == 404, "Nonexistent expense id should return 404"

    def test_post_nonexistent_expense_returns_404(self, client, app):
        with app.app_context():
            _set_session_user(client, _get_demo_user_id())

        resp = client.post(
            "/expenses/999999/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
        )
        assert resp.status_code == 404, "POST to nonexistent expense id should return 404"

    def test_get_other_users_expense_returns_404(self, client, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id)
            demo_id = _get_demo_user_id()
            _set_session_user(client, demo_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 404, (
            "Accessing another user's expense via GET should return 404"
        )

    def test_post_other_users_expense_returns_404(self, client, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id)
            demo_id = _get_demo_user_id()
            _set_session_user(client, demo_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
        )
        assert resp.status_code == 404, (
            "POST to another user's expense should return 404"
        )

    def test_post_other_users_expense_does_not_modify_db(self, client, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id, amount=88.0)
            demo_id = _get_demo_user_id()
            _set_session_user(client, demo_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "1.0",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "Tampered",
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["amount"] == 88.0, (
                "Cross-user POST must not modify the target expense"
            )


# ---------------------------------------------------------------------------
# GET — pre-filled form
# ---------------------------------------------------------------------------

class TestGetPrefilledForm:
    def test_get_valid_expense_returns_200(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200, "Valid GET should return 200"

    def test_get_form_contains_method_post(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b'method="POST"' in resp.data or b"method='POST'" in resp.data, (
            "Edit form must use method POST"
        )

    def test_get_form_prefills_amount(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=123.45)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        # The template renders expense.amount directly (Python float → template)
        assert b"123.45" in resp.data, (
            "Edit form must pre-fill the amount field with the stored value"
        )

    def test_get_form_prefills_date_in_iso_format(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, date="2026-01-20")
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"2026-01-20" in resp.data, (
            "Edit form must pre-fill the date in YYYY-MM-DD format"
        )

    def test_get_form_prefills_description(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description="My test note")
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"My test note" in resp.data, (
            "Edit form must pre-fill the description field"
        )

    def test_get_form_preselects_category(self, client, app):
        """The stored category option must carry the 'selected' attribute."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, category="Transport")
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        html = resp.data.decode()
        # Find the Transport option and confirm it has 'selected'
        # The template renders: <option value="Transport" selected>Transport</option>
        assert "Transport" in html, "Transport category must appear in the dropdown"
        transport_idx = html.index("Transport")
        # Look for 'selected' near the Transport option (within 80 chars before it)
        surrounding = html[max(0, transport_idx - 80):transport_idx + 80]
        assert "selected" in surrounding, (
            "The stored category option must be marked as selected"
        )

    def test_get_form_does_not_preselect_wrong_category(self, client, app):
        """Only the stored category should be selected; others must not be."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, category="Health")
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        html = resp.data.decode()
        # Count occurrences of 'selected' — should be exactly one
        assert html.count("selected") == 1, (
            "Exactly one category option should be marked as selected"
        )

    def test_get_form_contains_all_categories(self, client, app):
        """All 7 CATEGORIES must appear in the select dropdown."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        for cat in CATEGORIES:
            assert cat.encode() in resp.data, (
                f"Category '{cat}' must appear in the edit form dropdown"
            )

    def test_get_form_contains_save_changes_button(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"Save Changes" in resp.data, (
            "Edit form must include a 'Save Changes' submit button"
        )

    def test_get_form_contains_cancel_link_to_profile(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/edit")
        assert b"/profile" in resp.data, (
            "Edit form must contain a cancel link back to /profile"
        )


# ---------------------------------------------------------------------------
# POST — successful update
# ---------------------------------------------------------------------------

class TestPostSuccessfulUpdate:
    def test_valid_post_redirects_to_profile(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Successful POST must redirect"
        assert "/profile" in resp.headers["Location"], (
            "Successful update must redirect to /profile"
        )

    def test_valid_post_flashes_expense_updated(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
            follow_redirects=True,
        )
        assert b"Expense updated!" in resp.data, (
            "Successful update must flash 'Expense updated!'"
        )

    def test_valid_post_updates_amount_in_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=10.0)
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "75.0",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["amount"] == 75.0, "DB must reflect the updated amount"

    def test_valid_post_updates_category_in_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, category="Food")
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": "Shopping",
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["category"] == "Shopping", "DB must reflect the updated category"

    def test_valid_post_updates_date_in_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, date="2026-01-01")
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": "2026-04-10",
                "description": VALID_DESCRIPTION,
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["date"] == "2026-04-10", "DB must reflect the updated date"

    def test_valid_post_updates_description_in_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description="Old description")
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "Brand new description",
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["description"] == "Brand new description", (
                "DB must reflect the updated description"
            )

    def test_valid_post_does_not_affect_other_expenses(self, client, app):
        """Updating one expense must not touch other rows in the DB."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=10.0)
            other_id = _create_expense(user_id, amount=99.0)
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "55.0",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": VALID_DESCRIPTION,
            },
        )

        with app.app_context():
            other_row = _fetch_expense_row(other_id)
            assert other_row["amount"] == 99.0, (
                "Updating one expense must not modify other expense rows"
            )


# ---------------------------------------------------------------------------
# POST — optional blank description saves NULL
# ---------------------------------------------------------------------------

class TestPostBlankDescription:
    def test_blank_description_redirects_to_profile(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, (
            "Submitting with blank description should succeed and redirect"
        )
        assert "/profile" in resp.headers["Location"]

    def test_blank_description_stores_null_in_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description="Will be cleared")
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "",
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["description"] is None, (
                "Blank description submission must store NULL in the DB"
            )

    def test_whitespace_only_description_stores_null_in_db(self, client, app):
        """A description of only whitespace should be treated as blank (NULL)."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description="Has content")
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "   ",
            },
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["description"] is None, (
                "Whitespace-only description must be stored as NULL"
            )


# ---------------------------------------------------------------------------
# POST — validation errors
# ---------------------------------------------------------------------------

class TestPostValidationErrors:
    def _post_and_check(self, client, app, data, expected_fragment):
        """Helper: log in, create expense, POST bad data, assert 200 + error in body."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=data,
            follow_redirects=False,
        )
        assert resp.status_code == 200, (
            f"Validation error should re-render form (200), got {resp.status_code}"
        )
        assert expected_fragment.encode() in resp.data, (
            f"Expected error text '{expected_fragment}' in response"
        )
        return resp

    def test_missing_amount_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": "", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
            expected_fragment="Amount is required",
        )

    def test_zero_amount_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": "0", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
            expected_fragment="greater than zero",
        )

    def test_negative_amount_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": "-10", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
            expected_fragment="greater than zero",
        )

    def test_non_numeric_amount_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": "abc", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
            expected_fragment="Amount must be a number",
        )

    def test_invalid_category_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": VALID_AMOUNT, "category": "Gambling", "date": VALID_DATE, "description": ""},
            expected_fragment="valid category",
        )

    def test_empty_category_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": VALID_AMOUNT, "category": "", "date": VALID_DATE, "description": ""},
            expected_fragment="valid category",
        )

    def test_invalid_date_string_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": VALID_AMOUNT, "category": VALID_CATEGORY, "date": "not-a-date", "description": ""},
            expected_fragment="valid date",
        )

    def test_invalid_date_format_returns_error(self, client, app):
        """A date in DD/MM/YYYY format is not ISO-8601 and should fail."""
        self._post_and_check(
            client, app,
            data={"amount": VALID_AMOUNT, "category": VALID_CATEGORY, "date": "10/04/2026", "description": ""},
            expected_fragment="valid date",
        )

    def test_missing_date_returns_error(self, client, app):
        self._post_and_check(
            client, app,
            data={"amount": VALID_AMOUNT, "category": VALID_CATEGORY, "date": "", "description": ""},
            expected_fragment="valid date",
        )

    def test_validation_error_rerenders_form_not_redirect(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
            follow_redirects=False,
        )
        assert resp.status_code == 200, "Validation failure must re-render, not redirect"
        assert b"<form" in resp.data, "Re-rendered response must contain the edit form"

    def test_validation_error_retains_submitted_amount(self, client, app):
        """On error, the submitted (bad) amount should appear in the form, not the DB value."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "abc", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
        )
        assert b"abc" in resp.data, (
            "On validation error, the submitted amount value must be retained in the form"
        )

    def test_validation_error_retains_submitted_category(self, client, app):
        """On error, the submitted category should be retained in the re-rendered form."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, category="Food")
            _set_session_user(client, user_id)

        # Submit invalid date but valid category (Bills) — category should be retained
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": VALID_AMOUNT, "category": "Bills", "date": "bad-date", "description": ""},
        )
        html = resp.data.decode()
        # The submitted "Bills" category should appear selected in the error form
        bills_idx = html.index("Bills")
        surrounding = html[max(0, bills_idx - 80):bills_idx + 80]
        assert "selected" in surrounding, (
            "On validation error, the submitted category must be retained as selected"
        )

    def test_validation_error_does_not_modify_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=50.0)
            _set_session_user(client, user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "abc", "category": VALID_CATEGORY, "date": VALID_DATE, "description": ""},
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row["amount"] == 50.0, (
                "A validation failure must not modify the expense in the DB"
            )


# ---------------------------------------------------------------------------
# DB query helpers — unit tests
# ---------------------------------------------------------------------------

class TestGetExpenseByIdHelper:
    def test_returns_correct_dict_for_owner(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(
                user_id, amount=42.0, category="Bills",
                date="2026-06-01", description="Electricity"
            )
            result = get_expense_by_id(expense_id, user_id)

        assert result is not None, "get_expense_by_id must return a dict for the owner"
        assert result["id"] == expense_id
        assert result["amount"] == 42.0
        assert result["category"] == "Bills"
        assert result["date"] == "2026-06-01"
        assert result["description"] == "Electricity"

    def test_returns_none_for_nonexistent_id(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            result = get_expense_by_id(999999, user_id)

        assert result is None, (
            "get_expense_by_id must return None for a nonexistent expense id"
        )

    def test_returns_none_for_wrong_user(self, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id)
            demo_id = _get_demo_user_id()
            result = get_expense_by_id(expense_id, demo_id)

        assert result is None, (
            "get_expense_by_id must return None when user_id does not own the expense"
        )

    def test_returns_empty_string_for_null_description(self, app):
        """The helper should normalise a NULL description to an empty string."""
        with app.app_context():
            conn = get_db()
            user_id = _get_demo_user_id()
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (user_id, 10.0, "Other", "2026-06-01", None),
            )
            conn.commit()
            expense_id = cursor.lastrowid
            conn.close()

            result = get_expense_by_id(expense_id, user_id)

        assert result["description"] == "", (
            "get_expense_by_id must return '' (not None) when description is NULL"
        )


class TestUpdateExpenseHelper:
    def test_update_expense_persists_all_fields(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(
                user_id, amount=10.0, category="Food",
                date="2026-01-01", description="Original"
            )
            update_expense(expense_id, user_id, 99.99, "Entertainment", "2026-07-04", "Independence Day")
            row = _fetch_expense_row(expense_id)

        assert row["amount"] == 99.99
        assert row["category"] == "Entertainment"
        assert row["date"] == "2026-07-04"
        assert row["description"] == "Independence Day"

    def test_update_expense_with_none_description_stores_null(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description="Will be nulled")
            update_expense(expense_id, user_id, 20.0, "Other", "2026-06-01", None)
            row = _fetch_expense_row(expense_id)

        assert row["description"] is None, (
            "update_expense must store NULL when description=None is passed"
        )

    def test_update_expense_scoped_to_user(self, app):
        """update_expense with a wrong user_id must not change anything."""
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id, amount=50.0)
            demo_id = _get_demo_user_id()
            # Attempt to update other user's expense using demo_id
            update_expense(expense_id, demo_id, 1.0, "Other", "2026-01-01", "Hacked")
            row = _fetch_expense_row(expense_id)

        assert row["amount"] == 50.0, (
            "update_expense must be scoped to user_id — wrong user must not modify the row"
        )


# ---------------------------------------------------------------------------
# Parametrized validation cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("amount,category,date,expected_error", [
    ("",       "Food",      "2026-04-10",  "Amount is required"),
    ("0",      "Food",      "2026-04-10",  "greater than zero"),
    ("-5",     "Food",      "2026-04-10",  "greater than zero"),
    ("abc",    "Food",      "2026-04-10",  "Amount must be a number"),
    ("50",     "Gambling",  "2026-04-10",  "valid category"),
    ("50",     "",          "2026-04-10",  "valid category"),
    ("50",     "Food",      "not-a-date",  "valid date"),
    ("50",     "Food",      "",            "valid date"),
    ("50",     "Food",      "10/04/2026",  "valid date"),
])
def test_post_validation_parametrized(client, app, amount, category, date, expected_error):
    """Parametrized coverage of all POST validation failure paths."""
    with app.app_context():
        user_id = _get_demo_user_id()
        expense_id = _create_expense(user_id)
        _set_session_user(client, user_id)

    resp = client.post(
        f"/expenses/{expense_id}/edit",
        data={"amount": amount, "category": category, "date": date, "description": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 200, (
        f"Expected 200 re-render for invalid input (amount={amount!r}, category={category!r}, date={date!r})"
    )
    assert expected_error.encode() in resp.data, (
        f"Expected error '{expected_error}' for input (amount={amount!r}, category={category!r}, date={date!r})"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_very_large_amount_accepted(self, client, app):
        """A very large but valid positive float should be accepted."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "9999999.99",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "Large amount",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Very large valid amount should be accepted"

    def test_sql_injection_in_description_is_safe(self, client, app):
        """SQL injection via description must not raise an error (parameterised query)."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        malicious = "'; DROP TABLE expenses; --"
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": VALID_AMOUNT,
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": malicious,
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, (
            "SQL injection in description must not crash the route (parameterised queries protect it)"
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row is not None, "expenses table must still exist after SQL injection attempt"
            assert row["description"] == malicious, (
                "Malicious description string must be stored literally, not executed"
            )

    def test_amount_with_many_decimal_places_accepted(self, client, app):
        """Floats with many decimal places should be coerced and stored."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "12.123456789",
                "category": VALID_CATEGORY,
                "date": VALID_DATE,
                "description": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302, "Amount with many decimals is a valid float and should be accepted"

    def test_each_valid_category_is_accepted(self, client, app):
        """Every category in CATEGORIES must be accepted as a valid submission."""
        for cat in CATEGORIES:
            with app.app_context():
                user_id = _get_demo_user_id()
                expense_id = _create_expense(user_id)
                _set_session_user(client, user_id)

            resp = client.post(
                f"/expenses/{expense_id}/edit",
                data={
                    "amount": VALID_AMOUNT,
                    "category": cat,
                    "date": VALID_DATE,
                    "description": "category test",
                },
                follow_redirects=False,
            )
            assert resp.status_code == 302, (
                f"Category '{cat}' must be accepted as valid and result in a redirect"
            )
