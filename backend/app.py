from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from db import DB_PATH, close_db, get_db

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Flask will also serve the frontend files, so one command runs everything.
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.teardown_appcontext(close_db)

def error_response(message, status):
    return jsonify({"error": message}), status


def parse_price(param_name):
    """Return a float, None if absent, or raise ValueError if invalid."""
    raw = request.args.get(param_name, "").strip()
    if raw == "":
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"'{param_name}' must be a number")
    if value < 0:
        raise ValueError(f"'{param_name}' cannot be negative")
    return value


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/products")
def list_products():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    if len(search) > 100:
        return error_response("'search' must be 100 characters or fewer", 400)

    try:
        min_price = parse_price("min_price")
        max_price = parse_price("max_price")
    except ValueError as e:
        return error_response(str(e), 400)

    if min_price is not None and max_price is not None and min_price > max_price:
        return error_response("'min_price' cannot be greater than 'max_price'", 400)

    query = "SELECT id, name, description, price, image_url, category, stock FROM products"
    filters = []
    params = []

    if search:
        filters.append("(name LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if category:
        filters.append("category = ? COLLATE NOCASE")
        params.append(category)
    if min_price is not None:
        filters.append("price >= ?")
        params.append(min_price)
    if max_price is not None:
        filters.append("price <= ?")
        params.append(max_price)

    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id"

    # The ? placeholders keep user input separate from the SQL command.
    rows = get_db().execute(query, params).fetchall()
    products = [dict(row) for row in rows]
    return jsonify({"count": len(products), "products": products})


@app.get("/api/products/<int:product_id>")
def get_product(product_id):
    row = get_db().execute(
        "SELECT id, name, description, price, image_url, category, stock "
        "FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    if row is None:
        return error_response("Product not found", 404)
    return jsonify(dict(row))


@app.get("/api/categories")
def list_categories():
    rows = get_db().execute(
        "SELECT DISTINCT category FROM products ORDER BY category"
    ).fetchall()
    return jsonify([row["category"] for row in rows])


# --- JSON errors for API routes (instead of Flask's default HTML pages) ---
@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith("/api/"):
        return error_response("Resource not found", 404)
    return e


@app.errorhandler(405)
def handle_405(e):
    if request.path.startswith("/api/"):
        return error_response("Method not allowed", 405)
    return e


@app.errorhandler(500)
def handle_500(e):
    return error_response("Internal server error", 500)


if __name__ == "__main__":
    if not DB_PATH.exists():
        raise SystemExit("Database not found. Run: python backend/init_db.py")
    app.run(debug=True)