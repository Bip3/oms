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
