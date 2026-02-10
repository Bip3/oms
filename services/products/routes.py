from fastapi import APIRouter, HTTPException
from psycopg2.errors import IntegrityError, UniqueViolation

from shared.db import get_conn

from .models import ProductCreate, ProductOut, ProductUpdate
from .service import create_product, delete_product, get_product_by_id, update_product

router = APIRouter()


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product_endpoint(payload: ProductCreate):
    conn = get_conn()
    try:
        return create_product(
            conn,
            payload.sku,
            payload.name,
            payload.description,
            payload.price_cents,
            payload.stock_quantity,
            payload.is_active,
        )
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists")
    finally:
        conn.close()


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product_endpoint(product_id: int):
    conn = get_conn()
    try:
        row = get_product_by_id(conn, product_id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return row
    finally:
        conn.close()


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product_endpoint(product_id: int, payload: ProductUpdate):
    conn = get_conn()
    try:
        row = update_product(
            conn,
            product_id,
            payload.name,
            payload.description,
            payload.price_cents,
            payload.stock_quantity,
            payload.is_active,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return row
    finally:
        conn.close()


@router.delete("/products/{product_id}", status_code=204)
def delete_product_endpoint(product_id: int):
    conn = get_conn()
    try:
        deleted = delete_product(conn, product_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Product not found")
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Product is referenced by orders")
    finally:
        conn.close()
