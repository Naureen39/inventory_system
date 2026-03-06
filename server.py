import argparse
import os
import secrets
from datetime import date, datetime, timedelta
import sqlite3
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, url_for, flash, session

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "inventory.db"

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
APP_USERNAME = os.getenv("APP_USERNAME")
APP_PASSWORD = os.getenv("APP_PASSWORD")
AUTH_CONFIGURED = bool(APP_USERNAME and APP_PASSWORD)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)


@app.before_request
def require_login():
    allowed = {"login", "static"}
    if request.endpoint in allowed:
        return
    if session.get("logged_in"):
        return
    return redirect(url_for("login"))


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 5000")
        g.db.execute("PRAGMA journal_mode = WAL")
        g.db.execute("PRAGMA synchronous = FULL")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    cursor = db.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = FULL")

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


@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_CONFIGURED:
        flash("Login is not configured. Set APP_USERNAME and APP_PASSWORD on server.", "error")
        return render_template("login.html"), 503

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("stock"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


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


@app.post("/products/<int:product_id>/delete")
def delete_product(product_id):
    db = get_db()
    product = db.execute("SELECT id, name FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))

    has_purchase = db.execute("SELECT 1 FROM purchases WHERE product_id = ? LIMIT 1", (product_id,)).fetchone()
    has_sale = db.execute("SELECT 1 FROM sales WHERE product_id = ? LIMIT 1", (product_id,)).fetchone()
    if has_purchase or has_sale:
        flash("Cannot delete product with purchase/sale history.", "error")
        return redirect(url_for("products"))

    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    flash("Product deleted.", "success")
    return redirect(url_for("products"))


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for("products"))

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            category = request.form.get("category", "").strip()
            cost_price = parse_non_negative_float(request.form.get("cost_price"), "Cost price")
            sale_price = parse_non_negative_float(request.form.get("sale_price"), "Sale price")
            quantity = int(request.form.get("quantity", "0"))
            low_stock_limit = parse_positive_int(request.form.get("low_stock_limit"), "Low stock limit")

            if quantity < 0:
                raise ValueError("Quantity cannot be negative.")
            if not name:
                raise ValueError("Product name is required.")

            db.execute(
                """
                UPDATE products
                SET name = ?, category = ?, cost_price = ?, sale_price = ?, quantity = ?, low_stock_limit = ?
                WHERE id = ?
                """,
                (name, category, cost_price, sale_price, quantity, low_stock_limit, product_id),
            )
            db.commit()
            flash("Product updated.", "success")
            return redirect(url_for("products"))
        except sqlite3.IntegrityError:
            flash("Product name already exists.", "error")
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("edit_product.html", product=product)


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
        SELECT pu.id, p.name, pu.qty, pu.unit_cost, pu.purchased_at
        FROM purchases pu
        JOIN products p ON p.id = pu.product_id
        ORDER BY pu.id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("purchase.html", products=products_list, latest=latest)


@app.post("/purchase/<int:purchase_id>/delete")
def delete_purchase(purchase_id):
    db = get_db()
    row = db.execute(
        """
        SELECT pu.id, pu.product_id, pu.qty, p.name, p.quantity
        FROM purchases pu
        JOIN products p ON p.id = pu.product_id
        WHERE pu.id = ?
        """,
        (purchase_id,),
    ).fetchone()

    if not row:
        flash("Purchase record not found.", "error")
        return redirect(url_for("purchase"))

    new_qty = row["quantity"] - row["qty"]
    if new_qty < 0:
        flash("Cannot delete purchase now because stock is already consumed.", "error")
        return redirect(url_for("purchase"))

    db.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, row["product_id"]))
    db.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
    db.commit()
    flash("Purchase deleted and stock reverted.", "success")
    return redirect(url_for("purchase"))


@app.route("/purchase/<int:purchase_id>/edit", methods=["GET", "POST"])
def edit_purchase(purchase_id):
    db = get_db()
    row = db.execute(
        """
        SELECT pu.id, pu.product_id, pu.qty, pu.unit_cost, p.name, p.quantity
        FROM purchases pu
        JOIN products p ON p.id = pu.product_id
        WHERE pu.id = ?
        """,
        (purchase_id,),
    ).fetchone()
    if not row:
        flash("Purchase record not found.", "error")
        return redirect(url_for("purchase"))

    if request.method == "POST":
        try:
            new_qty = parse_positive_int(request.form.get("qty"), "Quantity")
            new_unit_cost = parse_non_negative_float(request.form.get("unit_cost"), "Unit cost")

            # Adjust stock by delta between new and old purchase qty.
            delta = new_qty - row["qty"]
            updated_stock = row["quantity"] + delta
            if updated_stock < 0:
                raise ValueError("Cannot reduce purchase qty because stock is already consumed.")

            db.execute(
                "UPDATE purchases SET qty = ?, unit_cost = ? WHERE id = ?",
                (new_qty, new_unit_cost, purchase_id),
            )
            db.execute("UPDATE products SET quantity = ? WHERE id = ?", (updated_stock, row["product_id"]))
            db.commit()
            flash("Purchase updated and stock adjusted.", "success")
            return redirect(url_for("purchase"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("edit_purchase.html", row=row)


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
        SELECT s.id, s.product_id, p.name, s.qty, s.unit_sale, s.unit_cost_snapshot, s.sold_at
        FROM sales s
        JOIN products p ON p.id = s.product_id
        ORDER BY s.id DESC
        LIMIT 20
        """
    ).fetchall()
    return render_template("sale.html", products=products_list, latest=latest)


@app.post("/sale/<int:sale_id>/delete")
def delete_sale(sale_id):
    db = get_db()
    row = db.execute(
        """
        SELECT s.id, s.product_id, s.qty, p.quantity
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.id = ?
        """,
        (sale_id,),
    ).fetchone()

    if not row:
        flash("Sale record not found.", "error")
        return redirect(url_for("sale"))

    new_qty = row["quantity"] + row["qty"]
    db.execute("UPDATE products SET quantity = ? WHERE id = ?", (new_qty, row["product_id"]))
    db.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    db.commit()
    flash("Sale deleted and stock reverted.", "success")
    return redirect(url_for("sale"))


@app.route("/sale/<int:sale_id>/edit", methods=["GET", "POST"])
def edit_sale(sale_id):
    db = get_db()
    row = db.execute(
        """
        SELECT s.id, s.product_id, s.qty, s.unit_sale, p.name, p.quantity
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.id = ?
        """,
        (sale_id,),
    ).fetchone()
    if not row:
        flash("Sale record not found.", "error")
        return redirect(url_for("sale"))

    if request.method == "POST":
        try:
            new_qty = parse_positive_int(request.form.get("qty"), "Quantity")
            new_unit_sale = parse_non_negative_float(request.form.get("unit_sale"), "Unit sale price")

            # Stock after replacing old qty with new qty.
            updated_stock = row["quantity"] + row["qty"] - new_qty
            if updated_stock < 0:
                raise ValueError("Not enough stock for updated sale quantity.")

            db.execute(
                "UPDATE sales SET qty = ?, unit_sale = ? WHERE id = ?",
                (new_qty, new_unit_sale, sale_id),
            )
            db.execute("UPDATE products SET quantity = ? WHERE id = ?", (updated_stock, row["product_id"]))
            db.commit()
            flash("Sale updated and stock adjusted.", "success")
            return redirect(url_for("sale"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("edit_sale.html", row=row)


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
