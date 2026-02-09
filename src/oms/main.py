from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

import psycopg2
from psycopg2.errors import UniqueViolation, IntegrityError

from .db import get_conn
from .products import create_product, get_product_by_id, update_product
from .orders import create_order, get_order_by_id, OutOfStockError
from .customers import create_customer, get_customer_by_id

app = FastAPI(title="OMS - Customers (psycopg2)", version="0.1.0")


#Schemas

class CustomerCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None

class CustomerOut(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str]
    created_at: datetime
    updated_at: datetime

class ProductCreate(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    price_cents: int
    stock_quantity: int
    is_active: bool = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price_cents: Optional[int] = None
    stock_quantity: Optional[int] = None
    is_active: Optional[bool] = None

class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    price_cents: int
    stock_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

class OrderItemIn(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    customer_id: int
    items: List[OrderItemIn]

class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    unit_price_cents: int
    line_total_cents: int

class OrderOut(BaseModel):
    id: int
    customer_id: int
    status: str
    total_cents: int
    items: List[OrderItemOut]
    created_at: datetime
    updated_at: datetime




#Endpoints
#@app.post -> fastapi defines route that handles an http request - post in this case.
@app.post("/customers", response_model=CustomerOut, status_code=201)
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
    #UniqueViolation exception for duplicate entries
    except UniqueViolation:
        #Rollback whatever we just tried to do
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    except IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Invalid customer data")
    
    finally:
        conn.close()

@app.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer_endpoint(customer_id: int):
    conn = get_conn()
    try:
        customer = get_customer_by_id(conn, customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        else:
            return customer
    finally:
        conn.close()
@app.post("/products", response_model=ProductOut, status_code=201)
def create_product_endpoint(payload: ProductCreate):
    conn = get_conn()
    try:
        return create_product(conn, payload.sku, payload.name, payload.description, payload.price_cents, payload.stock_quantity, payload.is_active)
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="SKU already exists")
    finally:
        conn.close()

@app.get("/products/{product_id}", response_model=ProductOut)
def get_product_endpoint(product_id: int):
    conn = get_conn()
    try:
        row = get_product_by_id(conn, product_id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return row
    finally:
        conn.close()

@app.put("/products/{product_id}", response_model=ProductOut)
def update_product_endpoint(product_id: int, payload: ProductUpdate):
    conn = get_conn()
    try:
        row = update_product(conn, product_id, payload.name, payload.description, payload.price_cents, payload.stock_quantity, payload.is_active)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found")
        return row
    finally:
        conn.close()

@app.post("/orders", response_model=OrderOut, status_code=201)
def create_order_endpoint(payload: OrderCreate):
    conn = get_conn()
    try:
        try:
            order = create_order(conn, payload.customer_id, [i.model_dump() for i in payload.items])
            return order
        except OutOfStockError as e:
            raise HTTPException(
                status_code=409,
                detail={"code": "OUT_OF_STOCK", "product_id": e.product_id, "available": e.available, "requested": e.requested},
            )
        except KeyError as e:
            msg = str(e)
            if msg == "'CUSTOMER_NOT_FOUND'":
                raise HTTPException(status_code=404, detail="Customer not found")
            if msg.startswith("'PRODUCT_NOT_FOUND:"):
                pid = msg.split(":")[1].strip("'")
                raise HTTPException(status_code=404, detail=f"Product not found: {pid}")
            raise
    finally:
        conn.close()

@app.get("/orders/{order_id}", response_model=OrderOut)
def get_order_endpoint(order_id: int):
    conn = get_conn()
    try:
        order = get_order_by_id(conn, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    finally:
        conn.close()

    
