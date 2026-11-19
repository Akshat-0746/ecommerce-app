import logging
import os
import time
import uuid
import math
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
try:
    from .db import DB_PATH, close_db, get_db
    from .security import check_password_hash, generate_password_hash
except ImportError:
    from db import DB_PATH, close_db, get_db
    from security import check_password_hash, generate_password_hash

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Flask will also serve the frontend files, so one command runs everything.
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "development-only-change-me")
app.teardown_appcontext(close_db)

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}',
)

HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
HTTP_ERRORS = Counter("http_request_errors_total", "HTTP error responses", ["method", "endpoint", "status"])
HTTP_LATENCY = Histogram("http_request_latency_seconds", "HTTP request latency", ["method", "endpoint"])
CART_OPERATIONS = Counter("cart_operations_total", "Completed cart operations", ["operation"])

def error_response(message, status):
    return jsonify({"error": message}), status


def current_user_id():
    return session.get("user_id")


def login_required():
    user_id = current_user_id()
    if user_id is None:
        return None, error_response("Authentication required", 401)
    return user_id, None


def admin_required():
    user_id = current_user_id()
    if user_id is None:
        return None, error_response("Authentication required", 401)
    user = get_db().execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        session.clear()
        return None, error_response("Authentication required", 401)
    if user["role"] != "admin":
        return None, error_response("Administrator access required", 403)
    return user_id, None


def parse_product_payload(data):
    if not isinstance(data, dict):
        return None, error_response("JSON body is required", 400)

    text_fields = ("name", "description", "image_url", "category")
    values = {field: data.get(field) for field in text_fields}
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            return None, error_response(f"'{field}' is required", 400)
        values[field] = value.strip()

    price = data.get("price")
    if isinstance(price, bool) or not isinstance(price, (int, float)):
        return None, error_response("'price' must be a non-negative number", 400)
    try:
        price = float(price)
    except OverflowError:
        return None, error_response("'price' must be a non-negative number", 400)
    if not math.isfinite(price) or price < 0:
        return None, error_response("'price' must be a non-negative number", 400)

    stock = data.get("stock")
    if isinstance(stock, bool) or not isinstance(stock, int) or not 0 <= stock <= 2**63 - 1:
        return None, error_response("'stock' must be an integer between 0 and 9223372036854775807", 400)

    if not values["image_url"].startswith(("http://", "https://")):
        return None, error_response("'image_url' must start with http:// or https://", 400)
    values["price"] = price
    values["stock"] = stock
    return values, None


def get_or_create_cart(user_id):
    db = get_db()
    row = db.execute("SELECT id FROM carts WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return row["id"]
    cursor = db.execute("INSERT INTO carts (user_id) VALUES (?)", (user_id,))
    db.commit()
    return cursor.lastrowid


@app.before_request
def start_request():
    request.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.started_at = time.perf_counter()


@app.after_request
def record_request(response):
    elapsed = time.perf_counter() - request.started_at
    endpoint = request.endpoint or "unknown"
    status = str(response.status_code)
    HTTP_REQUESTS.labels(request.method, endpoint, status).inc()
    HTTP_LATENCY.labels(request.method, endpoint).observe(elapsed)
    if response.status_code >= 400:
        HTTP_ERRORS.labels(request.method, endpoint, status).inc()
    response.headers["X-Request-ID"] = request.request_id
    logging.info(
        '{"request_id":"%s","method":"%s","path":"%s","status":%s,"duration_ms":%.2f}',
        request.request_id,
        request.method,
        request.path,
        response.status_code,
        elapsed * 1000,
    )
    return response


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


@app.post("/api/admin/products")
def create_product():
    _, error = admin_required()
    if error:
        return error
    values, error = parse_product_payload(request.get_json(silent=True))
    if error:
        return error
    db = get_db()
    cursor = db.execute(
        "INSERT INTO products (name, description, price, image_url, category, stock) "
        "VALUES (:name, :description, :price, :image_url, :category, :stock)",
        values,
    )
    db.commit()
    product = db.execute(
        "SELECT id, name, description, price, image_url, category, stock "
        "FROM products WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return jsonify(dict(product)), 201


@app.put("/api/admin/products/<int:product_id>")
def update_product(product_id):
    _, error = admin_required()
    if error:
        return error
    values, error = parse_product_payload(request.get_json(silent=True))
    if error:
        return error
    db = get_db()
    cursor = db.execute(
        "UPDATE products SET name = :name, description = :description, "
        "price = :price, image_url = :image_url, category = :category, "
        "stock = :stock WHERE id = :id",
        {**values, "id": product_id},
    )
    if cursor.rowcount == 0:
        return error_response("Product not found", 404)
    db.commit()
    product = db.execute(
        "SELECT id, name, description, price, image_url, category, stock "
        "FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()
    return jsonify(dict(product))


@app.delete("/api/admin/products/<int:product_id>")
def delete_product(product_id):
    _, error = admin_required()
    if error:
        return error
    db = get_db()
    product = db.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        return error_response("Product not found", 404)
    db.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
    db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    db.commit()
    return jsonify({"message": "Product deleted"})


@app.post("/api/auth/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("JSON body is required", 400)
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password")
    if not name or not email or not password:
        return error_response("Name, email, and password are required", 400)
    if len(password) < 8:
        return error_response("Password must be at least 8 characters", 400)
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'customer')",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        session["user_id"] = cursor.lastrowid
        session["user_name"] = name
        logging.info('{"event":"registration","request_id":"%s","user_id":%s}', request.request_id, cursor.lastrowid)
        return jsonify({"id": cursor.lastrowid, "name": name, "email": email, "role": "customer"}), 201
    except Exception as exc:
        db.rollback()
        if "UNIQUE constraint failed" in str(exc):
            return error_response("Email is already registered", 409)
        logging.exception('{"event":"database_error","request_id":"%s","operation":"register"}', request.request_id)
        return error_response("Internal server error", 500)


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("JSON body is required", 400)
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password")
    if not email or not password:
        return error_response("Email and password are required", 400)
    row = get_db().execute(
        "SELECT id, name, email, password_hash, role FROM users WHERE email = ?", (email,)
    ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        logging.warning('{"event":"failed_login","request_id":"%s","email":"%s"}', request.request_id, email)
        return error_response("Invalid email or password", 401)
    session.clear()
    session["user_id"] = row["id"]
    session["user_name"] = row["name"]
    logging.info('{"event":"login","request_id":"%s","user_id":%s}', request.request_id, row["id"])
    return jsonify({
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
    })


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


@app.get("/api/auth/me")
def auth_me():
    user_id, error = login_required()
    if error:
        return error
    row = get_db().execute(
        "SELECT id, name, email, role FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return jsonify(dict(row)) if row else error_response("User not found", 404)


@app.get("/api/cart")
def get_cart():
    user_id, error = login_required()
    if error:
        return error
    cart_id = get_or_create_cart(user_id)
    rows = get_db().execute(
        "SELECT ci.id, ci.product_id, ci.quantity, p.name, p.price, p.image_url "
        "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
        "WHERE ci.cart_id = ? ORDER BY ci.id",
        (cart_id,),
    ).fetchall()
    items = []
    total = 0.0
    for row in rows:
        item = dict(row)
        item["subtotal"] = round(item["price"] * item["quantity"], 2)
        total += item["subtotal"]
        items.append(item)
    return jsonify({"items": items, "total": round(total, 2), "count": sum(i["quantity"] for i in items)})


@app.post("/api/cart/items")
def add_cart_item():
    user_id, error = login_required()
    if error:
        return error
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("JSON body is required", 400)
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)
    if not isinstance(product_id, int) or isinstance(product_id, bool):
        return error_response("'product_id' must be an integer", 400)
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        return error_response("'quantity' must be a positive integer", 400)
    db = get_db()
    product = db.execute("SELECT id, stock FROM products WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        return error_response("Product not found", 404)
    cart_id = get_or_create_cart(user_id)
    existing = db.execute(
        "SELECT quantity FROM cart_items WHERE cart_id = ? AND product_id = ?",
        (cart_id, product_id),
    ).fetchone()
    new_quantity = quantity + (existing["quantity"] if existing else 0)
    if new_quantity > product["stock"]:
        return error_response("Requested quantity exceeds available stock", 400)
    if existing:
        db.execute(
            "UPDATE cart_items SET quantity = ? WHERE cart_id = ? AND product_id = ?",
            (new_quantity, cart_id, product_id),
        )
    else:
        db.execute(
            "INSERT INTO cart_items (cart_id, product_id, quantity) VALUES (?, ?, ?)",
            (cart_id, product_id, quantity),
        )
    db.execute("UPDATE carts SET updated_at = datetime('now') WHERE id = ?", (cart_id,))
    db.commit()
    CART_OPERATIONS.labels("add").inc()
    return jsonify({"message": "Product added to cart"}), 201


@app.put("/api/cart/items/<int:item_id>")
def update_cart_item(item_id):
    user_id, error = login_required()
    if error:
        return error
    data = request.get_json(silent=True)
    quantity = data.get("quantity") if isinstance(data, dict) else None
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
        return error_response("'quantity' must be a positive integer", 400)
    db = get_db()
    cart_id = get_or_create_cart(user_id)
    row = db.execute(
        "SELECT ci.product_id, p.stock FROM cart_items ci "
        "JOIN products p ON p.id = ci.product_id WHERE ci.id = ? AND ci.cart_id = ?",
        (item_id, cart_id),
    ).fetchone()
    if row is None:
        return error_response("Cart item not found", 404)
    if quantity > row["stock"]:
        return error_response("Requested quantity exceeds available stock", 400)
    db.execute("UPDATE cart_items SET quantity = ? WHERE id = ? AND cart_id = ?", (quantity, item_id, cart_id))
    db.execute("UPDATE carts SET updated_at = datetime('now') WHERE id = ?", (cart_id,))
    db.commit()
    CART_OPERATIONS.labels("update").inc()
    return jsonify({"message": "Cart item updated"})


@app.delete("/api/cart/items/<int:item_id>")
def remove_cart_item(item_id):
    user_id, error = login_required()
    if error:
        return error
    db = get_db()
    cart_id = get_or_create_cart(user_id)
    cursor = db.execute(
        "DELETE FROM cart_items WHERE id = ? AND cart_id = ?", (item_id, cart_id)
    )
    db.commit()
    if cursor.rowcount == 0:
        return error_response("Cart item not found", 404)
    CART_OPERATIONS.labels("remove").inc()
    return jsonify({"message": "Cart item removed"})


@app.get("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


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
    app.run(
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )