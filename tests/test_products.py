from datetime import datetime, timezone

from fastapi.testclient import TestClient
from psycopg2.errors import IntegrityError, UniqueViolation

from services.products.main import app
import services.products.routes as routes


def test_create_product_success(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_create_product(*_args, **_kwargs):
        return {
            "id": 1,
            "sku": "SKU-1",
            "name": "Widget",
            "description": None,
            "price_cents": 1999,
            "stock_quantity": 10,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "create_product", fake_create_product)

    client = TestClient(app)
    resp = client.post(
        "/products",
        json={
            "sku": "SKU-1",
            "name": "Widget",
            "price_cents": 1999,
            "stock_quantity": 10,
            "is_active": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["sku"] == "SKU-1"


def test_create_product_duplicate(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_create_product(*_args, **_kwargs):
        raise UniqueViolation()

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "create_product", fake_create_product)

    client = TestClient(app)
    resp = client.post(
        "/products",
        json={
            "sku": "SKU-1",
            "name": "Widget",
            "price_cents": 1999,
            "stock_quantity": 10,
            "is_active": True,
        },
    )
    assert resp.status_code == 409


def test_delete_product_referenced(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_delete_product(*_args, **_kwargs):
        raise IntegrityError()

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "delete_product", fake_delete_product)

    client = TestClient(app)
    resp = client.delete("/products/1")
    assert resp.status_code == 409


def test_get_product_not_found(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_get_product_by_id(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "get_product_by_id", fake_get_product_by_id)

    client = TestClient(app)
    resp = client.get("/products/999")
    assert resp.status_code == 404
