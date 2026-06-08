# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense record they own.
A "Delete" button is added to each row in the profile transaction table.
Clicking it submits a small inline form via POST to
`/expenses/<id>/delete`, which verifies ownership, performs the deletion,
flashes a confirmation message, and redirects back to `/profile`.
Using POST (not GET) ensures the delete cannot be triggered by a prefetch or
link crawl — this is the correct HTTP verb for a destructive state change.

## Depends on
- Step 1: Database setup (`expenses` table in place)
- Step 3: Login / Logout (`session["user_id"]` available)
- Step 4 / 5: Profile page exists and is the natural redirect target post-delete
- Step 8: Edit link already added per row; delete sits alongside it

## Routes
- `POST /expenses/<int:id>/delete` — verify ownership and delete the expense row — logged-in only

## Database changes
No schema changes. The `expenses` table already has all required columns.

One new query helper must be added to `database/queries.py`:
- `delete_expense(expense_id, user_id)` — executes
  `DELETE FROM expenses WHERE id = ? AND user_id = ?` using parameterised
  placeholders; returns `cursor.rowcount` so the route can detect a
  not-found / not-owned row.

## Templates
- **Modify**: `templates/profile.html`
  - Each row in the transaction table must gain a "Delete" form button
    alongside the existing "Edit" link.
  - The form wraps only the delete button:
    `<form method="post" action="{{ url_for('delete_expense', id=tx.id) }}">`
  - Submit button label: "Delete"
  - Style class: `btn-delete-expense` (mirrors `btn-edit-expense` convention)

## Files to change
- `app.py`
  - Replace the GET stub at `/expenses/<int:id>/delete` with a POST-only
    handler:
    - Redirect to `/login` if unauthenticated
    - Call `delete_expense(id, session["user_id"])`
    - If `rowcount == 0`, `abort(404)` (expense not found or not owned)
    - Flash "Expense deleted!" and redirect to `url_for("profile")`
  - Import `delete_expense` from `database.queries`
- `database/queries.py`
  - Add `delete_expense(expense_id, user_id)` — DELETE with ownership check,
    returns `cursor.rowcount`
- `templates/profile.html`
  - Add per-row inline POST form with a Delete button next to the Edit link

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Ownership check is mandatory: `WHERE id = ? AND user_id = ?` in
  `delete_expense` — never delete by id alone
- The route must be `POST` only — replace the GET stub entirely; a GET
  request to this URL should 405 (Flask's default for unregistered methods)
- Unauthenticated POST must redirect to `/login`
- If rowcount is 0 after DELETE, `abort(404)`
- After successful delete, flash "Expense deleted!" and redirect to
  `url_for("profile")`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹

## Definition of done
- [ ] A POST request to `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] A POST to `/expenses/<id>/delete` for a non-existent or other user's expense returns 404
- [ ] A POST to `/expenses/<id>/delete` for an owned expense deletes the row and redirects to `/profile`
- [ ] After deletion, the flash message "Expense deleted!" is visible on `/profile`
- [ ] The deleted expense no longer appears in the transaction list on `/profile`
- [ ] Each row in the profile transaction table has a "Delete" button that submits to the correct URL
- [ ] The "Edit" link per row is unaffected by this change
- [ ] A GET request to `/expenses/<id>/delete` returns 405 Method Not Allowed
