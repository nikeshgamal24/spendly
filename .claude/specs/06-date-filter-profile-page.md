# Spec: Date Filter for Profile Page

## Overview
Step 6 adds an optional date range filter to the `/profile` page so users can
narrow the transaction history, summary stats, and category breakdown to a
specific period. The filter is submitted as a GET form (query parameters `from`
and `to`), keeping the filtered URL bookmarkable and shareable. When no dates
are supplied the page behaves exactly as it did after Step 5 — all expenses are
shown. This step modifies no tables; it only threads optional date bounds through
the existing query helpers.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column exists)
- Step 2: Registration (users exist in the database)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 4: Profile page static UI (template structure already in place)
- Step 5: Backend routes for profile page (all four query helpers exist)

## Routes
- `GET /profile` — modified — accepts optional query params `from` and `to`
  (ISO date strings, e.g. `?from=2026-05-01&to=2026-05-31`) — logged-in only

No new routes.

## Database changes
No database changes. The `expenses.date` column (TEXT, stored as `YYYY-MM-DD`)
already supports range comparisons with `BETWEEN ? AND ?`.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter form above the bottom grid. The form uses `method="get"` and
    `action="{{ url_for('profile') }}"`.
  - Two `<input type="date">` fields: `name="from"` and `name="to"`.
  - A submit button labelled "Apply".
  - A "Clear" link that points to `url_for('profile')` with no query params.
  - Pre-fill the inputs with the currently active filter values so the user sees
    what range is applied.
  - Display an inline validation message (rendered by Jinja, not JS) when
    `from` > `to`.

## Files to change
- `app.py` — read `from` and `to` from `request.args`; validate that if both
  are present `from <= to`; pass them through to all four query helpers.
- `database/queries.py` — add optional `date_from=None` and `date_to=None`
  keyword arguments to `get_recent_transactions`, `get_summary_stats`, and
  `get_category_breakdown`. When both bounds are present, append
  `AND date BETWEEN ? AND ?` to the WHERE clause. `get_user_by_id` is unchanged.
- `templates/profile.html` — add the filter form as described above.
- `static/css/profile.css` — add styles for the filter form (`.profile-filter`).

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never f-strings or `.format()` in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- The filter form must use `method="get"` — never `method="post"`
- Date validation (from > to) must happen in the route, not in JS
- If only one of `from` / `to` is supplied, treat it as no filter (ignore both)
- The `limit=10` cap on `get_recent_transactions` must be removed when a date
  filter is active so the full filtered set is shown; when no filter is active,
  keep `limit=10` as the default
- Do not break the existing behaviour when no query params are present — all
  existing tests must still pass
- Use `abort(400)` if dates are present but `from > to`
- `date_from` and `date_to` must be passed back to the template as
  `filter_from` and `filter_to` so the form can pre-fill the inputs

## Definition of done
- [ ] Visiting `/profile` with no query params shows all 8 seed transactions and
  all 4 stat values unchanged from Step 5
- [ ] Visiting `/profile?from=2026-05-01&to=2026-05-15` shows only the 4
  transactions whose date falls within that range, and the stats reflect only
  those 4 transactions
- [ ] The filter form is pre-filled with the active `from` and `to` values after
  applying a filter
- [ ] Clicking "Clear" returns to `/profile` with no query params and all data
  is restored
- [ ] Supplying `?from=2026-05-31&to=2026-05-01` (from > to) returns HTTP 400
- [ ] Supplying only `?from=2026-05-01` (no `to`) shows all transactions, not a
  partial filter
- [ ] A new user with no expenses sees zero stats and an empty transaction list
  with or without date params — no errors thrown
