# OMS Microservices Demo

This repo contains a small order management system (OMS) split into services for customers, products, and orders.

## Run Instructions

Choose one path: Docker (recommended) or local Python + Postgres.

## Docker (Recommended)

1. Create local env file:

```bash
cp .env.example .env
```

2. Build and run:

```bash
docker compose up --build
```

3. Services are available at:
- Customers: `http://localhost:8001`
- Products: `http://localhost:8002`
- Orders/Reports: `http://localhost:8003`

Example:

```bash
curl -X POST http://localhost:8001/customers \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","first_name":"Ada","last_name":"Lovelace","phone":"555-1234"}'
```

## Local (Python + Postgres)

Prereqs:
- Python 3.12+
- Postgres 16+

1. Create and activate a virtualenv, then install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create a local env file and update `DATABASE_URL` to point at localhost:

```bash
cp .env.example .env
# Example:
# DATABASE_URL=postgresql://postgres:change_me@localhost:5432/oms_dev
```

3. Create the database and schema:

```bash
psql -U postgres -c "CREATE DATABASE oms_dev"
psql -U postgres -d oms_dev -f shared/schema.sql
```

4. Run each service (from repo root):

```bash
uvicorn services.customers.main:app --reload --port 8001
uvicorn services.products.main:app --reload --port 8002
uvicorn services.orders.main:app --reload --port 8003
```

## Tests

From the repo root:

```bash
pytest
```

## Service Ports

- Customers: `http://localhost:8001`
- Products: `http://localhost:8002`
- Orders/Reports: `http://localhost:8003`

## API (Endpoints + Schemas)

Live OpenAPI/Swagger:
- Customers: `http://localhost:8001/docs` (`/openapi.json`)
- Products: `http://localhost:8002/docs` (`/openapi.json`)
- Orders/Reports: `http://localhost:8003/docs` (`/openapi.json`)

### Customers Service

Endpoints:
- `POST /customers` -> `CustomerOut` (201) | body: `CustomerCreate`
- `GET /customers/{customer_id}` -> `CustomerOut`
- `PUT /customers/{customer_id}` -> `CustomerOut` | body: `CustomerUpdate`
- `DELETE /customers/{customer_id}` -> (204)

Schemas:
- `CustomerCreate`: `email`, `first_name`, `last_name`, `phone?`
- `CustomerUpdate`: `email?`, `first_name?`, `last_name?`, `phone?`
- `CustomerOut`: `id`, `email`, `first_name`, `last_name`, `phone?`, `created_at`, `updated_at`

### Products Service

Endpoints:
- `POST /products` -> `ProductOut` (201) | body: `ProductCreate`
- `GET /products/{product_id}` -> `ProductOut`
- `PUT /products/{product_id}` -> `ProductOut` | body: `ProductUpdate`
- `DELETE /products/{product_id}` -> (204)

Schemas:
- `ProductCreate`: `sku`, `name`, `description?`, `price_cents`, `stock_quantity`, `is_active`
- `ProductUpdate`: `name?`, `description?`, `price_cents?`, `stock_quantity?`, `is_active?`
- `ProductOut`: `id`, `sku`, `name`, `description?`, `price_cents`, `stock_quantity`, `is_active`, `created_at`, `updated_at`

### Orders/Reports Service

Endpoints:
- `POST /orders` -> `OrderOut` (201) | body: `OrderCreate`
- `GET /orders/{order_id}` -> `OrderOut`
- `PUT /orders/{order_id}` -> `OrderOut` | body: `OrderUpdate`
- `PATCH /orders/{order_id}/status` -> `OrderOut` | body: `OrderStatusUpdate`
- `DELETE /orders/{order_id}` -> (204)
- `GET /customers/{customer_id}/orders` -> `[OrderSummaryOut]`
- `GET /orders?start=...&end=...` -> `[OrderSummaryOut]`
- `GET /reports/top-products?start=...&end=...&limit=10` -> `[TopProductOut]`

Schemas:
- `OrderItemIn`: `product_id`, `quantity`
- `OrderCreate`: `customer_id`, `items` (`OrderItemIn[]`)
- `OrderUpdate`: `items` (`OrderItemIn[]`)
- `OrderStatusUpdate`: `status`
- `OrderItemOut`: `product_id`, `quantity`, `unit_price_cents`, `line_total_cents`
- `OrderOut`: `id`, `customer_id`, `status`, `total_cents`, `items` (`OrderItemOut[]`), `created_at`, `updated_at`
- `OrderSummaryOut`: `id`, `customer_id`, `status`, `total_cents`, `created_at`, `updated_at`
- `TopProductOut`: `product_id`, `sku`, `name`, `total_quantity`, `total_sales_cents`
