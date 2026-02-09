import os
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from oms.main import app

load_dotenv()


@pytest.fixture(scope="session")
def db_conn():
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    yield conn
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_schema(db_conn):
    schema_path = Path(__file__).resolve().parents[1] / "src" / "oms" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    with db_conn.cursor() as cur:
        cur.execute(schema_sql)
    db_conn.commit()


@pytest.fixture(autouse=True)
def reset_db(db_conn):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
                order_items,
                orders,
                products,
                customers
            RESTART IDENTITY
            CASCADE
            """
        )
    db_conn.commit()


@pytest.fixture()
def client():
    return TestClient(app)
