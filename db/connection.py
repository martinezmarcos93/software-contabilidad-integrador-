"""
db/connection.py — Conexión SQLite unificada
"""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "contabilidad.db"


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def conn_ctx():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    schema_path = Path(__file__).parent / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    with conn_ctx() as conn:
        conn.executescript(schema)
