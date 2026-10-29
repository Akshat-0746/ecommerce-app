DROP TABLE IF EXISTS products;

CREATE TABLE products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL,
    price       REAL    NOT NULL CHECK (price >= 0),
    image_url   TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE INDEX idx_products_category ON products (category);