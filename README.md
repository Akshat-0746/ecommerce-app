# ShopEasy Full-Stack E-Commerce Application

ShopEasy is a Flask, SQLite, HTML, CSS, and JavaScript e-commerce application.
It includes product browsing, authentication, persistent user carts, structured
logging, Prometheus metrics, and a provisioned Grafana dashboard.

## Prerequisites

- Python 3.9+
- Docker and Docker Compose
- A modern browser

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python backend/init_db.py
APP_HOST=0.0.0.0 APP_PORT=5001 python backend/app.py
```

Open http://127.0.0.1:5001. Set `SECRET_KEY` in the environment for a
non-development session secret. The example listens on port 5001 because
macOS Control Center may reserve port 5000; binding to `0.0.0.0` allows the
Prometheus container to scrape the app. Use this development server only on a
trusted network.

To apply user/cart migrations to an existing database without resetting products:

```bash
python backend/migrate.py
```

The migrations add `users`, `carts`, `cart_items`, and user roles and are safe
to rerun. Existing product records are preserved.

The sample catalogue uses product-matched Unsplash image URLs. An internet
connection is needed to load these photos; administrators can replace image
URLs from the product management page.

## Administrator product management

Normal registration always creates a customer account. To create the first
administrator (or promote an existing account), run this command from the
project root. It prompts for the password without showing it in the terminal:

```bash
python backend/create_admin.py
```

Sign in at http://127.0.0.1:5001/auth.html with that account. Administrators
are redirected to the product management page at
http://127.0.0.1:5001/admin.html, where they can add, edit, and delete products.
The product create/update/delete API routes re-check the account role on the
server for every request. Customers can browse and shop but cannot manage
products. Deleting a product also removes it from customers' carts.

## Architecture

- `frontend/` contains the static browser interface.
- `frontend/admin.html` and `frontend/js/admin.js` provide the admin product
  management interface.
- `backend/app.py` exposes product, authentication, admin, cart, and metrics APIs.
- `backend/db.py` manages SQLite connections.
- `backend/ecommerce.db` persists products, users, carts, and cart items.
- `backend/schema.sql` defines the product schema.
- `backend/migrations/` contains additive SQL migrations, including customer
  and administrator roles.
- `backend/create_admin.py` securely bootstraps an administrator account.
- `monitoring/` contains Prometheus and Grafana configuration.

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/products` | Search/filter/list products |
| GET | `/api/products/<id>` | Get product details |
| GET | `/api/categories` | List product categories |
| POST | `/api/admin/products` | Add a product (administrator only) |
| PUT | `/api/admin/products/<id>` | Update a product (administrator only) |
| DELETE | `/api/admin/products/<id>` | Delete a product (administrator only) |
| POST | `/api/auth/register` | Register and create a session |
| POST | `/api/auth/login` | Authenticate and create a session |
| POST | `/api/auth/logout` | End the session |
| GET | `/api/auth/me` | Get the current authenticated user |
| GET | `/api/cart` | Get the current user's cart and total |
| POST | `/api/cart/items` | Add a product to the user's cart |
| PUT | `/api/cart/items/<id>` | Change an owned cart item's quantity |
| DELETE | `/api/cart/items/<id>` | Remove an owned cart item |
| GET | `/metrics` | Prometheus metrics endpoint |

Cart and cart-item operations are authorized by the server-side session user
ID. The backend always reads product prices and stock from SQLite, never from
client-submitted values.

## Monitoring

With the Flask application running on port 5001:

```bash
docker compose up -d
```

- Prometheus: http://127.0.0.1:9090
- Grafana: http://127.0.0.1:3001
- Grafana credentials: `admin` / `admin`
- The `E-Commerce / E-Commerce Monitoring` dashboard is provisioned
  automatically.

Generate traffic in the browser or with `curl`. Trigger a controlled 404
error and a failed login to demonstrate error metrics and structured logs:

```bash
curl -i http://127.0.0.1:5001/api/products/999999
curl -i -H 'Content-Type: application/json' \
  -d '{"email":"nobody@example.com","password":"wrongpassword"}' \
  http://127.0.0.1:5001/api/auth/login
```

The application logs timestamps, levels, request IDs, API methods/paths,
status codes, duration, failed authentication attempts, database errors, and
unexpected exceptions. Passwords and session cookies are never logged.
