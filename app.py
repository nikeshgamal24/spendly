import os
from datetime import date as _date
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, find_user_by_email, create_user
from database.queries import (
    get_user_by_id, get_recent_transactions, get_summary_stats,
    get_category_breakdown, insert_expense, get_expense_by_id,
    update_expense, CATEGORIES,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"  # TODO: use env var in production


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _validate_expense_form(raw_amount, category, raw_date):
    """Returns (amount_float, None) on success or (None, error_str) on failure."""
    if not raw_amount:
        return None, "Amount is required."
    try:
        amount = float(raw_amount)
        if amount <= 0:
            return None, "Amount must be greater than zero."
    except ValueError:
        return None, "Amount must be a number."

    if category not in CATEGORIES:
        return None, "Please select a valid category."

    try:
        _date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return None, "Please enter a valid date (YYYY-MM-DD)."

    return amount, None


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("register.html")

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")

    error = None
    if not name or not email or not password or not confirm:
        error = "All fields are required."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != confirm:
        error = "Passwords do not match."
    elif find_user_by_email(email):
        error = "An account with that email already exists."

    if error:
        return render_template("register.html", error=error, name=name, email=email)

    create_user(name, email, password)
    flash("Account created! Please sign in.")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    error = None
    if not email or not password:
        error = "Invalid email or password."

    if not error:
        user = find_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."

    if error:
        return render_template("login.html", error=error, email=email)

    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        abort(403)

    date_from_raw = request.args.get("from", "").strip()
    date_to_raw   = request.args.get("to",   "").strip()

    if date_from_raw and date_to_raw:
        try:
            d_from = _date.fromisoformat(date_from_raw)
            d_to   = _date.fromisoformat(date_to_raw)
        except ValueError:
            abort(400)
        if d_from > d_to:  # ISO dates sort correctly as strings, but compare as dates here
            abort(400)
        date_from, date_to = date_from_raw, date_to_raw
    else:
        date_from = date_to = None

    stats        = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        filter_from=date_from,
        filter_to=date_to,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("add_expense.html", categories=CATEGORIES, today=_date.today().isoformat())

    raw_amount  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    raw_date    = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    amount, error = _validate_expense_form(raw_amount, category, raw_date)

    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            error=error,
            form={"amount": raw_amount, "category": category, "date": raw_date, "description": description},
        )

    insert_expense(session["user_id"], amount, category, raw_date, description)
    flash("Expense added!")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    expense = get_expense_by_id(expense_id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=CATEGORIES,
            selected_category=expense["category"],
        )

    raw_amount  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    raw_date    = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    amount, error = _validate_expense_form(raw_amount, category, raw_date)

    if error:
        return render_template(
            "edit_expense.html",
            expense=expense,
            categories=CATEGORIES,
            selected_category=category,
            error=error,
            form={"amount": raw_amount, "category": category, "date": raw_date, "description": description},
        )

    rows_updated = update_expense(expense_id, session["user_id"], amount, category, raw_date, description)
    if rows_updated == 0:
        abort(404)
    flash("Expense updated!")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


with app.app_context():
    init_db()
    seed_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5001)
