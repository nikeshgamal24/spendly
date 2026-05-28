# Spec: Login and Logout

## Overview
Implement credential-based login and session-based logout. The `GET /login` route
already renders `login.html` with a working form — this step adds the `POST /login`
handler that validates the submitted email and password against the database, starts
a Flask session on success, and shows an inline error on failure. The `GET /logout`
stub is replaced with a handler that clears the session and redirects to the landing
page. `base.html` is updated so the nav reflects the user's logged-in state.

## Depends on
- Step 01 — Database Setup (`get_db`, `init_db`, `seed_db`)
- Step 02 — Registration (`find_user_by_email`, `users` table with `password_hash`)

## Routes
- `POST /login` — Validate credentials, set session, redirect to profile — public
- `GET /logout` — Clear session, redirect to landing — logged-in (no hard guard yet; guard added in Step 4)

## Database changes
No new tables or columns.

One new helper function in `database/db.py`:
- `get_user_by_id(user_id)` — returns a `sqlite3.Row` or `None`; needed so future
  routes can reload the current user from the session's `user_id`.

`find_user_by_email` already exists from Step 02 — no change needed.

## Templates
- **Modify:** `templates/login.html`
  - The form already has `method="POST" action="{{ url_for('login') }}"` — no change needed there.
  - Repopulate the email field on error: add `value="{{ email or '' }}"` to the email input.
- **Modify:** `templates/base.html`
  - Replace the hardcoded nav links with a conditional block:
    - Logged in (`session.user_id` is set): show "Profile" (`url_for('profile')`) and "Sign out" (`url_for('logout')`)
    - Logged out: show current "Sign in" and "Get started" links

## Files to change
- `app.py` — add POST handler to `login` route; import `session`, `check_password_hash`; implement `logout` route
- `database/db.py` — add `get_user_by_id(user_id)`
- `templates/login.html` — repopulate email on error
- `templates/base.html` — conditional nav based on `session`

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — no f-strings in SQL
- Passwords verified with `werkzeug.security.check_password_hash`
- Never reveal which field (email vs password) was wrong — always use a generic message: `"Invalid email or password."`
- Store only `user_id` and `user_name` in the session — never the password hash
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `logout` must call `session.clear()` (not `session.pop`) to wipe all session data
- Use `url_for()` for every redirect — never hardcode paths
- After successful login, redirect to `url_for('profile')`
- After logout, redirect to `url_for('landing')`

## Definition of done
- [ ] Submitting correct credentials sets `session['user_id']` and redirects to `/profile`
- [ ] Submitting a wrong password shows "Invalid email or password." inline without clearing the email field
- [ ] Submitting an unregistered email shows the same generic error
- [ ] Submitting with a blank field is rejected (HTML5 `required` + server-side check)
- [ ] Visiting `/logout` clears the session and redirects to `/`
- [ ] After logout, revisiting `/login` shows no session data in the nav
- [ ] Nav shows "Profile" and "Sign out" when logged in; "Sign in" and "Get started" when logged out
- [ ] `get_user_by_id()` is importable and returns `None` for a non-existent ID
- [ ] App starts without errors (`python app.py`)
- [ ] `pytest` passes (no regressions)
