import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "ecommerce.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        for script in ("schema.sql", "seed.sql"):
            sql = (BASE_DIR / script).read_text(encoding="utf-8")
            conn.executescript(sql)
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"Database ready at {DB_PATH} with {count} products.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()