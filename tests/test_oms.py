from datetime import datetime, timezone


def test_create_customer_and_get(client):
    payload = {
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Ng",
        "phone": "555-0001",
    }
    res = client.post("/customers", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == 1
    assert data["email"] == payload["email"]

    res_get = client.get(f"/customers/{data['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["email"] == payload["email"]


def test_create_product_and_get(client):
    payload = {
        "sku": "SKU-1",
        "name": "Widget",
        "description": "A widget",
        "price_cents": 1299,
        "stock_quantity": 10,
        "is_active": True,
    }
    res = client.post("/products", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == 1
    assert data["sku"] == "SKU-1"

    res_get = client.get(f"/products/{data['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["stock_quantity"] == 10


def test_create_order_decrements_stock(client):
    cust = client.post(
        "/customers",
        json={
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Lee",
            "phone": "555-0002",
        },
    ).json()
    prod = client.post(
        "/products",
        json={
            "sku": "SKU-2",
            "name": "Gizmo",
            "description": "A gizmo",
            "price_cents": 500,
            "stock_quantity": 5,
            "is_active": True,
        },
    ).json()

    order = client.post(
        "/orders",
        json={"customer_id": cust["id"], "items": [{"product_id": prod["id"], "quantity": 2}]},
    )
    assert order.status_code == 201
    order_data = order.json()
    assert order_data["total_cents"] == 1000

    prod_after = client.get(f"/products/{prod['id']}").json()
    assert prod_after["stock_quantity"] == 3


def test_update_order_items_restock(client):
    cust = client.post(
        "/customers",
        json={
            "email": "cara@example.com",
            "first_name": "Cara",
            "last_name": "Kim",
            "phone": "555-0003",
        },
    ).json()
    prod = client.post(
        "/products",
        json={
            "sku": "SKU-3",
            "name": "Thing",
            "description": "A thing",
            "price_cents": 200,
            "stock_quantity": 5,
            "is_active": True,
        },
    ).json()

    order = client.post(
        "/orders",
        json={"customer_id": cust["id"], "items": [{"product_id": prod["id"], "quantity": 2}]},
    ).json()

    updated = client.put(
        f"/orders/{order['id']}",
        json={"items": [{"product_id": prod["id"], "quantity": 1}]},
    )
    assert updated.status_code == 200
    updated_data = updated.json()
    assert updated_data["total_cents"] == 200

    prod_after = client.get(f"/products/{prod['id']}").json()
    assert prod_after["stock_quantity"] == 4


def test_status_transitions_and_cancel_restock(client):
    cust = client.post(
        "/customers",
        json={
            "email": "dana@example.com",
            "first_name": "Dana",
            "last_name": "Quinn",
            "phone": "555-0004",
        },
    ).json()
    prod = client.post(
        "/products",
        json={
            "sku": "SKU-4",
            "name": "Part",
            "description": "A part",
            "price_cents": 300,
            "stock_quantity": 5,
            "is_active": True,
        },
    ).json()

    order = client.post(
        "/orders",
        json={"customer_id": cust["id"], "items": [{"product_id": prod["id"], "quantity": 2}]},
    ).json()

    res_confirm = client.patch(f"/orders/{order['id']}/status", json={"status": "CONFIRMED"})
    assert res_confirm.status_code == 200
    assert res_confirm.json()["status"] == "CONFIRMED"

    res_cancel = client.patch(f"/orders/{order['id']}/status", json={"status": "CANCELLED"})
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    prod_after = client.get(f"/products/{prod['id']}").json()
    assert prod_after["stock_quantity"] == 5

    res_invalid = client.patch(f"/orders/{order['id']}/status", json={"status": "SHIPPED"})
    assert res_invalid.status_code == 409


def test_reports(client):
    cust = client.post(
        "/customers",
        json={
            "email": "erin@example.com",
            "first_name": "Erin",
            "last_name": "Lo",
            "phone": "555-0005",
        },
    ).json()
    prod_a = client.post(
        "/products",
        json={
            "sku": "SKU-5",
            "name": "Alpha",
            "description": "A",
            "price_cents": 100,
            "stock_quantity": 10,
            "is_active": True,
        },
    ).json()
    prod_b = client.post(
        "/products",
        json={
            "sku": "SKU-6",
            "name": "Beta",
            "description": "B",
            "price_cents": 200,
            "stock_quantity": 10,
            "is_active": True,
        },
    ).json()

    client.post(
        "/orders",
        json={
            "customer_id": cust["id"],
            "items": [
                {"product_id": prod_a["id"], "quantity": 2},
                {"product_id": prod_b["id"], "quantity": 1},
            ],
        },
    )

    orders_for_customer = client.get(f"/customers/{cust['id']}/orders")
    assert orders_for_customer.status_code == 200
    assert len(orders_for_customer.json()) == 1

    start = "2000-01-01T00:00:00Z"
    end = "2100-01-01T00:00:00Z"
    orders_by_date = client.get(f"/orders?start={start}&end={end}")
    assert orders_by_date.status_code == 200
    assert len(orders_by_date.json()) == 1

    top = client.get(f"/reports/top-products?start={start}&end={end}&limit=10")
    assert top.status_code == 200
    top_data = top.json()
    assert len(top_data) == 2
    assert top_data[0]["total_quantity"] >= top_data[1]["total_quantity"]


def test_edge_cases(client):
    cust = client.post(
        "/customers",
        json={
            "email": "edge@example.com",
            "first_name": "Edge",
            "last_name": "Case",
            "phone": "555-2000",
        },
    ).json()

    prod = client.post(
        "/products",
        json={
            "sku": "SKU-EDGE",
            "name": "EdgeWidget",
            "description": "Edge product",
            "price_cents": 250,
            "stock_quantity": 1,
            "is_active": True,
        },
    ).json()

    # Out-of-stock on create
    res = client.post(
        "/orders",
        json={
            "customer_id": cust["id"],
            "items": [{"product_id": prod["id"], "quantity": 2}],
        },
    )
    assert res.status_code == 409

    # Valid order
    order = client.post(
        "/orders",
        json={
            "customer_id": cust["id"],
            "items": [{"product_id": prod["id"], "quantity": 1}],
        },
    ).json()

    # Non-PENDING edit should fail
    res = client.patch(f"/orders/{order['id']}/status", json={"status": "CONFIRMED"})
    assert res.status_code == 200
    res = client.put(
        f"/orders/{order['id']}",
        json={"items": [{"product_id": prod["id"], "quantity": 1}]},
    )
    assert res.status_code == 409

    # Invalid transition: CONFIRMED -> DELIVERED
    res = client.patch(f"/orders/{order['id']}/status", json={"status": "DELIVERED"})
    assert res.status_code == 409

    # Invalid status value
    res = client.patch(f"/orders/{order['id']}/status", json={"status": "NOT_A_STATUS"})
    assert res.status_code == 400

    # Inactive product ordered
    inactive = client.post(
        "/products",
        json={
            "sku": "SKU-INACTIVE",
            "name": "Inactive",
            "description": "Inactive product",
            "price_cents": 100,
            "stock_quantity": 5,
            "is_active": False,
        },
    ).json()

    res = client.post(
        "/orders",
        json={
            "customer_id": cust["id"],
            "items": [{"product_id": inactive["id"], "quantity": 1}],
        },
    )
    assert res.status_code == 409
