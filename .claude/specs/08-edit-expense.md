# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user edit an existing expense record. The route
`GET /expenses/<id>/edit` renders a pre-filled form identical in structure to
the add-expense form. `POST /expenses/<id>/edit` validates the submission and
updates the row. Ownership is enforced: a user can only edit their own expenses.
A per-row "Edit" link is added to the transaction table on the profile page to
make the feature discoverable.

## Depends on
- Step 1: Database setup (`expenses` table schema in place)
- Step 3: Login / Logout (`session["user_id"]` available)
- Step 4 / 5: Profile page exists and is the natural redirect target after saving
- Step 7: `CATEGORIES` list and form structure already established in `add_expense.html`

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the existing expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense row — logged-in only

## Database changes
No schema changes. The `expenses` table already has all required columns.

Two new query helpers must be added to `database/queries.py`:
- `get_expense_by_id(expense_id, user_id)` — fetches a single expense row by its `id`, scoped to `user_id` so cross-user access is impossible at the query level; returns `None` if not found or not owned by the user.
- `update_expense(expense_id, user_id, amount, category, date, description)` — executes `UPDATE expenses SET ... WHERE id = ? AND user_id = ?` using parameterised placeholders.

`get_recent_transactions` must also be updated to include the expense `id` field in each returned dict, so the profile template can generate edit/delete links per row.

## Templates
- **Create**: `templates/edit_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action` pointing to `url_for("edit_expense", id=expense.id)`
  - Fields (identical to `add_expense.html`, pre-populated with current values):
    - `amount` — number input, step="0.01", min="0.01", required
    - `category` — `<select>` with the 7 fixed options, current category pre-selected
    - `date` — `<input type="date">`, required, pre-filled with current date (YYYY-MM-DD)
    - `description` — text input, optional, pre-filled with current value
  - Submit button ("Save Changes") and a cancel link back to `/profile`
  - Display an error message when validation fails, retaining the invalid submitted values (not the original DB values)

- **Modify**: `templates/profile.html`
  - Each row in the transaction table must gain an "Edit" link pointing to `url_for("edit_expense", id=transaction.id)`
  - This requires `get_recent_transactions` to include `id` in its returned dicts (see Database changes above)

## Files to change
- `app.py`
  - Replace the GET-only stub at `/expenses/<int:id>/edit` with a GET + POST handler:
    - Both methods: redirect to `/login` if unauthenticated; call `get_expense_by_id(id, session["user_id"])`; `abort(404)` if the result is `None`
    - GET: render `edit_expense.html`, passing `expense`, `categories=CATEGORIES`
    - POST: read and validate form fields (same rules as add-expense); on error re-render with error and submitted values; on success call `update_expense(...)`, flash "Expense updated!", redirect to `url_for("profile")`
- `database/queries.py`
  - Add `get_expense_by_id(expense_id, user_id)`
  - Add `update_expense(expense_id, user_id, amount, category, date, description)`
  - Update `get_recent_transactions` to `SELECT id, date, description, category, amount` so `id` is included in returned dicts
- `templates/profile.html`
  - Add per-row Edit link using the `id` field now available on each transaction dict

## Files to create
- `templates/edit_expense.html` — the edit-expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Ownership check is mandatory: `WHERE id = ? AND user_id = ?` in both `get_expense_by_id` and `update_expense` — never fetch by id alone
- Unauthenticated access to both GET and POST must redirect to `/login`
- If the expense does not exist or belongs to another user, `abort(404)`
- Validation rules for POST (same as Step 7):
  - `amount`: required, positive number > 0 (parse with `float()`; catch `ValueError`)
  - `category`: required, must be one of the 7 fixed CATEGORIES
  - `date`: required, valid `YYYY-MM-DD` (parse with `_date.fromisoformat()`)
  - `description`: optional; strip whitespace; store `None` if blank
  - On any validation error, re-render with error and submitted (not DB) values
- After successful update, flash "Expense updated!" and redirect to `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for a non-existent or other user's expense returns 404
- [ ] Visiting `/expenses/<id>/edit` while logged in shows a form pre-filled with the existing amount, category, date, and description
- [ ] The category dropdown has the correct option pre-selected
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in the transaction list
- [ ] Submitting with a missing or zero amount re-renders the form with an error and retains submitted values
- [ ] Submitting with an invalid category re-renders the form with an error
- [ ] Submitting with an invalid date re-renders the form with an error
- [ ] Submitting without a description saves `NULL` for description (no error)
- [ ] Each row in the profile transaction table has an "Edit" link that navigates to the correct edit URL
