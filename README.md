# ShopEasy

A small store website built with Flask, SQLite, HTML, CSS, and JavaScript.

## Run the project

From the project folder:

```bash
python -m pip install -r requirements.txt
python backend/init_db.py
python backend/app.py
```

Open <http://127.0.0.1:5000> in your browser. The database setup script creates
`backend/ecommerce.db` and adds the sample products. Running the setup script
again resets the products table to the sample data.

## How it works

- `backend/app.py` starts the Flask website and provides the product API.
- `backend/db.py` opens and closes the SQLite database connection.
- `backend/schema.sql` describes the products table.
- `backend/seed.sql` contains the sample products.
- `frontend/index.html` shows the product list and filters.
- `frontend/products.html` shows one product's details.
- `frontend/js/` contains the JavaScript that requests data from Flask and
  displays it.
- `frontend/css/style.css` styles both pages.

The browser asks Flask for product data using URLs such as `/api/products`.
Flask reads that data from SQLite and sends it back as JSON.
