import sqlite3
from pathlib import Path

from flask import g

DB_PATH = Path(__file__).parent / "ecommerce.db"


def get_db():
    """Open one connection per request and reuse it within that request."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row  # rows behave like dicts
    return g.db


def close_db(error=None):
    """Close the connection when the request ends."""
    db = g.pop("db", None)
    if db is not None:
        db.close()