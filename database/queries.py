from database.db import get_db


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    name = row["name"]
    created_at = row["created_at"]  # "YYYY-MM-DD HH:MM:SS"

    year, month_num = created_at[:4], int(created_at[5:7])
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    member_since = f"{month_names[month_num - 1]} {year}"

    words = name.split()
    initials = "".join(w[0].upper() for w in words if w)[:2]

    return {
        "name": name,
        "email": row["email"],
        "member_since": member_since,
        "initials": initials,
    }


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT date, description, category, amount
            FROM expenses
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    month_abbr = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    transactions = []
    for row in rows:
        raw_date = row["date"]  # "YYYY-MM-DD"
        year, month_num, day = raw_date[:4], int(raw_date[5:7]), raw_date[8:10]
        formatted_date = f"{day} {month_abbr[month_num - 1]} {year}"
        transactions.append({
            "date": formatted_date,
            "description": row["description"] or "",
            "category": row["category"],
            "amount": f"₹{row['amount']:.2f}",
        })
    return transactions


def get_summary_stats(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*), SUM(amount) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        transaction_count = row[0] or 0
        total_amount = row[1] or 0.0

        if transaction_count == 0:
            return {"total_spent": "₹0.00", "transaction_count": 0, "top_category": "—"}

        top_row = conn.execute(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY cat_total DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    top_category = top_row["category"] if top_row else "—"
    return {
        "total_spent": f"₹{total_amount:.2f}",
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT category, SUM(amount) AS cat_total
            FROM expenses
            WHERE user_id = ?
            GROUP BY category
            ORDER BY cat_total DESC
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    grand_total = sum(row["cat_total"] for row in rows)
    results = []
    for row in rows:
        raw_pct = row["cat_total"] / grand_total * 100
        results.append({
            "name": row["category"],
            "amount": f"₹{row['cat_total']:.2f}",
            "pct": round(raw_pct),
            "_raw_pct": raw_pct,
        })

    # Adjust largest category to absorb rounding remainder so pct sums to 100.
    remainder = 100 - sum(r["pct"] for r in results)
    if remainder != 0:
        results[0]["pct"] += remainder

    for r in results:
        del r["_raw_pct"]

    return results
