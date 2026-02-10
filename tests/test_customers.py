from datetime import datetime, timezone

from fastapi.testclient import TestClient
from psycopg2.errors import IntegrityError, UniqueViolation

from services.customers.main import app
import services.customers.routes as routes


def test_create_customer_success(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_create_customer(*_args, **_kwargs):
        return {
            "id": 1,
            "email": "a@example.com",
            "first_name": "A",
            "last_name": "User",
            "phone": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "create_customer", fake_create_customer)

    client = TestClient(app)
    resp = client.post(
        "/customers",
        json={"email": "a@example.com", "first_name": "A", "last_name": "User"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == 1


def test_create_customer_duplicate(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_create_customer(*_args, **_kwargs):
        raise UniqueViolation()

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "create_customer", fake_create_customer)

    client = TestClient(app)
    resp = client.post(
        "/customers",
        json={"email": "a@example.com", "first_name": "A", "last_name": "User"},
    )
    assert resp.status_code == 409


def test_get_customer_not_found(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_get_customer_by_id(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "get_customer_by_id", fake_get_customer_by_id)

    client = TestClient(app)
    resp = client.get("/customers/999")
    assert resp.status_code == 404


def test_delete_customer_has_orders(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_delete_customer(*_args, **_kwargs):
        raise IntegrityError()

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "delete_customer", fake_delete_customer)

    client = TestClient(app)
    resp = client.delete("/customers/1")
    assert resp.status_code == 409
