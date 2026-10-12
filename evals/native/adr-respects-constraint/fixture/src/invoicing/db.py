"""Database access for invoicing-service (Postgres 16 through psycopg 3)."""

import os
from contextlib import contextmanager

import psycopg


@contextmanager
def connect():
    conn = psycopg.connect(os.environ["INVOICING_DATABASE_URL"], autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
