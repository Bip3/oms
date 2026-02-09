# OMS API Documentation

Base URL: `http://localhost:8000`

## Customers
- `POST /customers`
```json
{
  "email": "user@example.com",
  "first_name": "Ada",
  "last_name": "Lovelace",
  "phone": "555-1234"
}
```

- `GET /customers/{customer_id}`

- `PUT /customers/{customer_id}`
```json
{
  "email": "new@example.com",
  "first_name": "Ada",
  "last_name": "Lovelace",
  "phone": "555-5678"
}
```

- `DELETE /customers/{customer_id}`
Returns `204` on success.

## Products
- `POST /products`
```json
{
  "sku": "SKU-123",
  "name": "Widget",
  "description": "A useful widget",
  "price_cents": 1299,
  "stock_quantity": 50,
  "is_active": true
}
```

- `GET /products/{product_id}`

- `PUT /products/{product_id}`
```json
{
  "name": "Widget v2",
  "price_cents": 1399,
  "stock_quantity": 40,
  "is_active": true
}
```

- `DELETE /products/{product_id}`
Returns `204` on success.

## Orders
- `POST /orders`
```json
{
  "customer_id": 1,
  "items": [
    { "product_id": 10, "quantity": 2 },
    { "product_id": 11, "quantity": 1 }
  ]
}
```

- `GET /orders/{order_id}`

- `PUT /orders/{order_id}`  
Only allowed when order status is `PENDING`.
```json
{
  "items": [
    { "product_id": 10, "quantity": 1 },
    { "product_id": 12, "quantity": 3 }
  ]
}
```

- `PATCH /orders/{order_id}/status`
```json
{ "status": "CONFIRMED" }
```
Allowed transitions:
- `PENDING -> CONFIRMED` or `CANCELLED`
- `CONFIRMED -> SHIPPED` or `CANCELLED`
- `SHIPPED -> DELIVERED`

- `DELETE /orders/{order_id}`  
Only allowed when order status is `PENDING`. Restores inventory.

## Reports and Queries
- `GET /customers/{customer_id}/orders`  
Returns order summaries for the customer.

- `GET /orders?start=2026-01-01T00:00:00Z&end=2026-01-31T23:59:59Z`  
Returns orders within the date range (inclusive).

- `GET /reports/top-products?start=2026-01-01T00:00:00Z&end=2026-01-31T23:59:59Z&limit=10`
Returns top-selling products by total quantity. Cancelled orders are excluded.
