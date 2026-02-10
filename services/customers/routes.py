from fastapi import APIRouter, HTTPException
from psycopg2.errors import IntegrityError, UniqueViolation

from shared.db import get_conn

from .models import CustomerCreate, CustomerOut, CustomerUpdate
from .service import create_customer, delete_customer, get_customer_by_id, update_customer

router = APIRouter()


@router.post("/customers", response_model=CustomerOut, status_code=201)
def create_customer_endpoint(payload: CustomerCreate):
    conn = get_conn()
    try:
        customer = create_customer(
            conn,
            email=str(payload.email),
            first_name=payload.first_name,
            last_name=payload.last_name,
            phone=payload.phone,
        )
        return customer
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Invalid customer data")
    finally:
        conn.close()


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer_endpoint(customer_id: int):
    conn = get_conn()
    try:
        customer = get_customer_by_id(conn, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return customer
    finally:
        conn.close()


@router.put("/customers/{customer_id}", response_model=CustomerOut)
def update_customer_endpoint(customer_id: int, payload: CustomerUpdate):
    conn = get_conn()
    try:
        row = update_customer(
            conn,
            customer_id,
            payload.email,
            payload.first_name,
            payload.last_name,
            payload.phone,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        return row
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    finally:
        conn.close()


@router.delete("/customers/{customer_id}", status_code=204)
def delete_customer_endpoint(customer_id: int):
    conn = get_conn()
    try:
        deleted = delete_customer(conn, customer_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Customer not found")
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Customer has existing orders")
    finally:
        conn.close()
