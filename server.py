import argparse
import os
from datetime import date, datetime
import sqlite3
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, url_for, flash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "inventory.db"

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = "dev-secret-change-me"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            cost_price REAL NOT NULL,
            sale_price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            low_stock_limit INTEGER NOT NULL DEFAULT 5,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            purchased_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_sale REAL NOT NULL,
            unit_cost_snapshot REAL NOT NULL,
            sold_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """
    )

    db.commit()
    db.close()


def parse_positive_int(value, field_name):
    try:
        parsed = int(value)
        if parsed <= 0:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive number.")


def parse_non_negative_float(value, field_name):
    try:
        parsed = float(value)
        if parsed < 0:
            raise ValueError
        return parsed
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a non-negative number.")


@app.route("/")
def index():
    return redirect(url_for("stock"))


@app.route("/products", methods=["GET", "POST"])
def products():
    db = get_db()

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            cost_price = parse_non_negative_float(request.form.get("cost_price"), "Cost price")
            sale_price = parse_non_negative_float(request.form.get("sale_price"), "Sale price")
            quantity = parse_positive_int(request.form.get("quantity"), "Quantity")
            low_stock_limit = parse_positive_int(request.form.get("low_stock_limit"), "Low stock limit")

            if not name:
                raise ValueError("Product name is required.")

            db.execute(
                """
                INSERT INTO products(name, category, cost_price, sale_price, quantity, low_stock_limit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (name, category, cost_price, sale_price, quantity, low_stock_limit, datetime.now().isoformat()),
            )
            db.commit()
            flash("Product added.", "success")
            return redirect(url_for("products"))
        except sqlite3.IntegrityError:
            flash("Product name already exists.", "error")
        except ValueError as exc:
            flash(str(exc), "error")

    items = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("products.html", items=items)


@app.route("/purchase", methods=["GET", "POST"])
def purchase():
    db = get_db()

    if request.method == "POST":
        try:
            product_id = parse_positive_int(request.form.get("product_id"), "Product")
            qty = parse_positive_int(request.form.get("qty"), "Quantity")
            unit_cost = parse_non_negative_float(request.form.get("unit_cost"), "Unit cost")

            product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not product:
                raise ValueError("Invalid product selected.")

            old_qty = product["quantity"]
            old_cost = product["cost_price"]
            new_qty = old_qty + qty

            # Weighted average for cost price.
            new_cost = ((old_qty * old_cost) + (qty * unit_cost)) / new_qty if new_qty else old_cost

            db.execute(
                "INSERT INTO purchases(product_id, qty, unit_cost, purchased_at) VALUES (?, ?, ?, ?)",
                (product_id, qty, unit_cost, datetime.now().isoformat()),
            )
            db.execute(
                "UPDATE products SET quantity = ?, cost_price = ? WHERE id = ?",
                (new_qty, round(new_cost, 2), product_id),
            )
            db.commit()
            flash("Purchase recorded and stock updated.", "success")
            return redirect(url_for("purchase"))
        except ValueError as exc:
            flash(str(exc), "error")

    products_list = db.execute("SELECT id, name FROM products ORDER BY name").fetchall()
    latest = db.execute(
        """
        SELECT p.name, pu.qty, pu.unit_cost, pu.purchased_at
        FROM purchases pu
        JOIN products p ON p.id = pu.product_id
        ORDER BY pu.id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("purchase.html", products=products_list, latest=latest)


@app.route("/sale", methods=["GET", "POST"])
def sale():
    db = get_db()

    if request.method == "POST":
        try:
            product_id = parse_positive_int(request.form.get("product_id"), "Product")
            qty = parse_positive_int(request.form.get("qty"), "Quantity")
            unit_sale = parse_non_negative_float(request.form.get("unit_sale"), "Unit sale price")

            product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
            if not product:
                raise ValueError("Invalid product selected.")
            if product["quantity"] < qty:
                raise ValueError("Insufficient stock for this sale.")

            new_qty = product["quantity"] - qty

            db.execute(
                """
                INSERT INTO sales(product_id, qty, unit_sale, unit_cost_snapshot, sold_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, qty, unit_sale, product["cost_price"], datetime.now().isoformat()),
            )
            db.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, product_id))
            db.commit()
            flash("Sale recorded and stock reduced.", "success")
            return redirect(url_for("sale"))
        except ValueError as exc:
            flash(str(exc), "error")

    products_list = db.execute("SELECT id, name, sale_price, quantity FROM products ORDER BY name").fetchall()
    latest = db.execute(
        """
        SELECT p.name, s.qty, s.unit_sale, s.unit_cost_snapshot, s.sold_at
        FROM sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("sale.html", products=products_list, latest=latest)


@app.route("/stock")
def stock():
    db = get_db()
    items = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("stock.html", items=items)


@app.route("/summary")
def summary():
    db = get_db()
    selected_date = request.args.get("date") or date.today().isoformat()

    day_sales = db.execute(
        """
        SELECT p.name, s.qty, s.unit_sale, s.unit_cost_snapshot,
               (s.qty * s.unit_sale) AS sale_total,
               (s.qty * s.unit_cost_snapshot) AS cost_total,
               (s.qty * (s.unit_sale - s.unit_cost_snapshot)) AS profit
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE date(s.sold_at) = ?
        ORDER BY s.id DESC
        """,
        (selected_date,),
    ).fetchall()

    totals = db.execute(
        """
        SELECT
            COALESCE(SUM(qty * unit_sale), 0) AS total_sales,
            COALESCE(SUM(qty * unit_cost_snapshot), 0) AS total_cost,
            COALESCE(SUM(qty * (unit_sale - unit_cost_snapshot)), 0) AS total_profit
        FROM sales
        WHERE date(sold_at) = ?
        """,
        (selected_date,),
    ).fetchone()

    return render_template("summary.html", day_sales=day_sales, totals=totals, selected_date=selected_date)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Inventory MVP server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")))
    args = parser.parse_args()

    init_db()
    app.run(debug=True, port=args.port)
