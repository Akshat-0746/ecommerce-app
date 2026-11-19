import sqlite3
from pathlib import Path

try:
    from .db_migrations import apply_migrations
except ImportError:
    from db_migrations import apply_migrations

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "ecommerce.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executescript((BASE_DIR / "seed.sql").read_text(encoding="utf-8"))
        apply_migrations(conn)
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"Database ready at {DB_PATH} with {count} products.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()