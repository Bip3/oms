from datetime import datetime, timezone

from fastapi.testclient import TestClient

from services.orders.main import app
import services.orders.routes as routes
import services.orders.service as service


def test_create_order_out_of_stock(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_create_order(*_args, **_kwargs):
        raise service.OutOfStockError(product_id=1, available=1, requested=5)

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "create_order", fake_create_order)

    client = TestClient(app)
    resp = client.post(
        "/orders",
        json={"customer_id": 1, "items": [{"product_id": 1, "quantity": 5}]},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["code"] == "OUT_OF_STOCK"


def test_get_order_not_found(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_get_order_by_id(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "get_order_by_id", fake_get_order_by_id)

    client = TestClient(app)
    resp = client.get("/orders/123")
    assert resp.status_code == 404


def test_update_order_invalid_status(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_update_order_status(*_args, **_kwargs):
        raise ValueError("INVALID_STATUS")

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "update_order_status", fake_update_order_status)

    client = TestClient(app)
    resp = client.patch("/orders/1/status", json={"status": "BOGUS"})
    assert resp.status_code == 400


def test_list_customer_orders(monkeypatch, dummy_conn):
    def fake_get_conn():
        return dummy_conn

    def fake_list_orders_by_customer(*_args, **_kwargs):
        return [
            {
                "id": 1,
                "customer_id": 1,
                "status": "PENDING",
                "total_cents": 1999,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ]

    monkeypatch.setattr(routes, "get_conn", fake_get_conn)
    monkeypatch.setattr(routes, "list_orders_by_customer", fake_list_orders_by_customer)

    client = TestClient(app)
    resp = client.get("/customers/1/orders")
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == 1
