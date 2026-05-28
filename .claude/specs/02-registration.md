# Spec: Registration

## Overview
Implement user registration so new visitors can create a Spendly account.
The existing `GET /register` route already renders the form — this step adds the
`POST /register` handler that validates input, inserts a hashed-password user row,
starts a session, and redirects to the login page. It also adds the DB helpers
(`create_user`, `find_user_by_email`) that both this step and the upcoming login
step will share. Also on sucess the user is shown with a sucess message and then redirected to the login page.

## Depends on
- Step 01 — Database Setup (`database/db.py` functions and schema must exist)

## Routes
- `POST /register` — Process registration form, create user, start session, redirect — public

## Database changes
No new tables. Two new helper functions added to `database/db.py`:

- `find_user_by_email(email)` — returns a `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes password with werkzeug, inserts row, returns new `user_id`

## Templates
- **Modify:** `templates/register.html`
  - Fix hardcoded `action="/register"` → `action="{{ url_for('register') }}"`
  - Add a confirm-password field (`name="confirm_password"`) before the submit button
  - Load `register.css` via `{% block head %}<link …>{% endblock %}`

## Files to change
- `app.py` — add POST handler to existing `register` route; import `request`, `redirect`, `url_for`, `session`; add `app.secret_key`
- `database/db.py` — add `find_user_by_email()` and `create_user()`
- `templates/register.html` — fix action URL, add confirm-password field, add CSS link

## Files to create
- `static/css/register.css` — page-specific styles for the auth form (`.auth-section`, `.auth-card`, `.auth-error`, etc.)

## New dependencies
No new dependencies. `werkzeug.security` is already installed.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only
- Parameterised queries only — no f-strings in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- `app.secret_key` must be set before any `session` usage (use a hard-coded dev string for now; flag that it must be env-var in production)
- Use CSS variables — never hardcode hex values in `register.css`
- All templates must extend `base.html`
- Route function has one responsibility: validate → call DB helper → set session → redirect or re-render
- On error, re-render `register.html` passing `error=` and `name=`/`email=` so the user doesn't lose their input
- Use `url_for()` for every internal redirect — never hardcode paths

## Definition of done
- [ ] Submitting valid new-user data creates a row in `users` with a hashed password (verify via `sqlite3 spendly.db "SELECT email, password_hash FROM users"`)
- [ ] After successful registration, the browser is redirected to `/login`
- [ ] Registering with an already-used email shows an inline error on the form without clearing the name/email fields
- [ ] Submitting mismatched passwords shows an inline error
- [ ] Submitting a password shorter than 8 characters shows an inline error
- [ ] Submitting with any blank field shows an inline error (HTML5 `required` + server-side check)
- [ ] The form action uses `url_for('register')`, not a hardcoded string
- [ ] `static/css/register.css` is loaded only on the register page
- [ ] App starts without errors (`python app.py`)
- [ ] `pytest` passes (no regressions)
