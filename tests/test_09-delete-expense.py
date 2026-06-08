"""
tests/test_09-delete-expense.py
Tests for the Delete Expense feature (Step 9).

Spec: .claude/specs/09-delete-expense.md
Routes under test:
  POST /expenses/<int:id>/delete
"""

import uuid
import pytest
from database.db import get_db, create_user
from database.queries import delete_expense


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_demo_user_id():
    """Return the id of the seeded demo user."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
    ).fetchone()
    conn.close()
    return row["id"]


def _create_expense(user_id, amount=50.0, category="Food",
                    date="2026-03-15", description="Test expense"):
    """Insert a test expense directly into the DB and return its id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
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


def _fetch_expense_row(expense_id):
    """Read raw expense row from DB — returns None when deleted."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return row


def _set_session_user(client, user_id):
    """Directly inject user_id into the Flask session."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def _post_delete(client, expense_id, follow_redirects=False):
    """POST to the delete endpoint for the given expense id."""
    return client.post(
        f"/expenses/{expense_id}/delete",
        follow_redirects=follow_redirects,
    )


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_post_redirects_to_login(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        resp = _post_delete(client, expense_id, follow_redirects=False)
        assert resp.status_code == 302, (
            "Unauthenticated POST must return a 302 redirect"
        )
        assert "/login" in resp.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_unauthenticated_post_does_not_delete_from_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        _post_delete(client, expense_id)

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row is not None, (
                "Unauthenticated POST must not remove the expense from the DB"
            )


# ---------------------------------------------------------------------------
# HTTP method guard
# ---------------------------------------------------------------------------

class TestHttpMethodGuard:
    def test_get_request_returns_405(self, client, app):
        """GET to the delete URL must be rejected with 405 Method Not Allowed."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 405, (
            "GET to a POST-only delete route must return 405 Method Not Allowed"
        )

    def test_get_request_unauthenticated_also_returns_405(self, client, app):
        """Even without a session, a GET to the delete URL should return 405,
        because Flask checks the method before the route handler runs."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)

        resp = client.get(f"/expenses/{expense_id}/delete")
        assert resp.status_code == 405, (
            "GET to a POST-only delete route must always return 405"
        )


# ---------------------------------------------------------------------------
# Ownership and 404 handling
# ---------------------------------------------------------------------------

class TestOwnershipAnd404:
    def test_post_nonexistent_expense_returns_404(self, client, app):
        with app.app_context():
            _set_session_user(client, _get_demo_user_id())

        resp = _post_delete(client, 999999)
        assert resp.status_code == 404, (
            "POST to a nonexistent expense id must return 404"
        )

    def test_post_other_users_expense_returns_404(self, client, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id)
            demo_id = _get_demo_user_id()
            _set_session_user(client, demo_id)

        resp = _post_delete(client, expense_id)
        assert resp.status_code == 404, (
            "POST to another user's expense must return 404"
        )

    def test_post_other_users_expense_does_not_delete_from_db(self, client, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id, amount=77.0)
            demo_id = _get_demo_user_id()
            _set_session_user(client, demo_id)

        _post_delete(client, expense_id)

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row is not None, (
                "Cross-user POST must not delete the target expense from the DB"
            )
            assert row["amount"] == 77.0, (
                "The other user's expense must remain unchanged after the cross-user attempt"
            )


# ---------------------------------------------------------------------------
# Happy path — successful deletion
# ---------------------------------------------------------------------------

class TestSuccessfulDelete:
    def test_valid_post_returns_302(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = _post_delete(client, expense_id, follow_redirects=False)
        assert resp.status_code == 302, (
            "Successful delete must return a 302 redirect"
        )

    def test_valid_post_redirects_to_profile(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = _post_delete(client, expense_id, follow_redirects=False)
        assert "/profile" in resp.headers["Location"], (
            "Successful delete must redirect to /profile"
        )

    def test_valid_post_removes_row_from_db(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        _post_delete(client, expense_id)

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row is None, (
                "After successful delete the expense row must not exist in the DB"
            )

    def test_valid_post_flashes_expense_deleted(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = _post_delete(client, expense_id, follow_redirects=True)
        assert b"Expense deleted!" in resp.data, (
            "Successful delete must flash 'Expense deleted!' visible on the profile page"
        )

    def test_valid_post_flash_message_on_profile_page(self, client, app):
        """The flash must appear in the full page response after following the redirect."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = _post_delete(client, expense_id, follow_redirects=True)
        assert resp.status_code == 200, (
            "Following the redirect after delete must land on a 200 profile page"
        )
        assert b"Expense deleted!" in resp.data, (
            "The flash message 'Expense deleted!' must be visible on the profile page"
        )

    def test_deleted_expense_not_in_profile_transactions(self, client, app):
        """After deletion the expense description must no longer appear in the
        transaction list rendered on /profile."""
        unique_desc = f"Unique expense {uuid.uuid4().hex[:6]}"
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, description=unique_desc)
            _set_session_user(client, user_id)

        _post_delete(client, expense_id)

        resp = client.get("/profile")
        assert unique_desc.encode() not in resp.data, (
            "Deleted expense description must not appear in the profile transaction list"
        )

    def test_delete_does_not_affect_other_expenses(self, client, app):
        """Deleting one expense must leave other expenses in the DB untouched."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=10.0)
            other_expense_id = _create_expense(user_id, amount=99.0, description="Keep me")
            _set_session_user(client, user_id)

        _post_delete(client, expense_id)

        with app.app_context():
            other_row = _fetch_expense_row(other_expense_id)
            assert other_row is not None, (
                "Deleting one expense must not remove other expense rows"
            )
            assert other_row["amount"] == 99.0, (
                "Other expense's amount must remain intact after an unrelated delete"
            )


# ---------------------------------------------------------------------------
# Profile template — Delete button presence and structure
# ---------------------------------------------------------------------------

class TestProfileDeleteButton:
    def test_profile_shows_delete_button_for_each_expense(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            _create_expense(user_id, description="Row one")
            _set_session_user(client, user_id)

        resp = client.get("/profile")
        assert resp.status_code == 200, "Profile page must return 200"
        assert b"btn-delete-expense" in resp.data, (
            "Profile page must contain an element with class 'btn-delete-expense'"
        )

    def test_profile_delete_button_label_is_delete(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get("/profile")
        assert b"Delete" in resp.data, (
            "Profile page must contain a button labelled 'Delete'"
        )

    def test_profile_delete_form_uses_post_method(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get("/profile")
        html = resp.data.decode()
        # The inline delete form must declare method="post" (case-insensitive)
        assert 'method="post"' in html.lower(), (
            "The delete form on the profile page must use method='post'"
        )

    def test_profile_delete_form_action_points_to_delete_route(self, client, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get("/profile")
        assert f"/expenses/{expense_id}/delete".encode() in resp.data, (
            "The delete form action must point to /expenses/<id>/delete for the correct expense"
        )

    def test_profile_edit_link_still_present_alongside_delete_button(self, client, app):
        """The Delete button must not displace the Edit link — both must appear per row."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        resp = client.get("/profile")
        assert b"btn-edit-expense" in resp.data, (
            "Edit link (btn-edit-expense) must still be present after the Delete button was added"
        )
        assert f"/expenses/{expense_id}/edit".encode() in resp.data, (
            "The Edit href must point to /expenses/<id>/edit for the correct expense"
        )

    def test_profile_has_delete_button_for_each_user_expense(self, client, app):
        """Each newly inserted expense must produce exactly one more delete form."""
        with app.app_context():
            user_id = _get_demo_user_id()
            # Count delete forms before adding new expenses
            _set_session_user(client, user_id)

        resp_before = client.get("/profile")
        count_before = resp_before.data.count(b"btn-delete-expense")

        with app.app_context():
            _create_expense(user_id, description="Extra row A")
            _create_expense(user_id, description="Extra row B")

        resp_after = client.get("/profile")
        count_after = resp_after.data.count(b"btn-delete-expense")

        assert count_after == count_before + 2, (
            "Adding two expenses must add exactly two more Delete buttons to the profile page"
        )


# ---------------------------------------------------------------------------
# delete_expense() query helper — unit tests
# ---------------------------------------------------------------------------

class TestDeleteExpenseHelper:
    def test_returns_1_for_owned_expense(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            rowcount = delete_expense(expense_id, user_id)

        assert rowcount == 1, (
            "delete_expense must return rowcount=1 when the expense is owned by the user"
        )

    def test_actually_removes_row_from_db(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            delete_expense(expense_id, user_id)
            row = _fetch_expense_row(expense_id)

        assert row is None, (
            "delete_expense must remove the expense row from the DB"
        )

    def test_returns_0_for_nonexistent_expense(self, app):
        with app.app_context():
            user_id = _get_demo_user_id()
            rowcount = delete_expense(999999, user_id)

        assert rowcount == 0, (
            "delete_expense must return rowcount=0 for a nonexistent expense id"
        )

    def test_returns_0_for_wrong_user(self, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id)
            demo_id = _get_demo_user_id()
            rowcount = delete_expense(expense_id, demo_id)

        assert rowcount == 0, (
            "delete_expense must return rowcount=0 when the user_id does not own the expense"
        )

    def test_does_not_delete_row_for_wrong_user(self, app):
        with app.app_context():
            other_id = _create_other_user()
            expense_id = _create_expense(other_id, amount=55.0)
            demo_id = _get_demo_user_id()
            delete_expense(expense_id, demo_id)
            row = _fetch_expense_row(expense_id)

        assert row is not None, (
            "delete_expense must not remove a row owned by a different user"
        )
        assert row["amount"] == 55.0, (
            "The other user's expense must be completely untouched"
        )

    def test_does_not_delete_sibling_expense(self, app):
        """Deleting one expense must leave sibling expenses of the same user intact."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id, amount=10.0)
            sibling_id = _create_expense(user_id, amount=20.0)
            delete_expense(expense_id, user_id)
            sibling_row = _fetch_expense_row(sibling_id)

        assert sibling_row is not None, (
            "Deleting one expense must not remove other expenses belonging to the same user"
        )
        assert sibling_row["amount"] == 20.0


# ---------------------------------------------------------------------------
# Parametrized ownership / auth cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expense_id", [0, -1, 999999, 2147483647])
def test_post_delete_with_invalid_or_absent_id_returns_404(client, app, expense_id):
    """Any expense id that does not exist in the DB must yield 404."""
    with app.app_context():
        _set_session_user(client, _get_demo_user_id())

    resp = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)
    assert resp.status_code == 404, (
        f"POST with nonexistent expense id={expense_id} must return 404"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_expenses_table_still_exists_after_delete(self, client, app):
        """Verify the expenses table is not dropped — sanity check for parameterised queries."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        _post_delete(client, expense_id)

        with app.app_context():
            conn = get_db()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'"
            ).fetchone()
            conn.close()
            assert tables is not None, (
                "expenses table must still exist after a delete operation"
            )

    def test_delete_same_expense_twice_second_call_returns_404(self, client, app):
        """Deleting an already-deleted expense must return 404 on the second attempt."""
        with app.app_context():
            user_id = _get_demo_user_id()
            expense_id = _create_expense(user_id)
            _set_session_user(client, user_id)

        _post_delete(client, expense_id)  # first delete — succeeds
        resp = _post_delete(client, expense_id, follow_redirects=False)  # second delete
        assert resp.status_code == 404, (
            "A second POST to delete an already-deleted expense must return 404"
        )

    def test_delete_expense_with_null_description_succeeds(self, client, app):
        """An expense without a description (NULL) must be deletable without error."""
        with app.app_context():
            user_id = _get_demo_user_id()
            conn = get_db()
            cursor = conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, 15.0, "Other", "2026-06-01", None),
            )
            conn.commit()
            expense_id = cursor.lastrowid
            conn.close()
            _set_session_user(client, user_id)

        resp = _post_delete(client, expense_id, follow_redirects=False)
        assert resp.status_code == 302, (
            "Deleting an expense with a NULL description must succeed with a 302 redirect"
        )

        with app.app_context():
            row = _fetch_expense_row(expense_id)
            assert row is None, (
                "Expense with NULL description must be removed from the DB after delete"
            )
