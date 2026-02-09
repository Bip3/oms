from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

import psycopg2
from psycopg2.errors import UniqueViolation, IntegrityError

from .db import get_conn
from .products import create_product, get_product_by_id, update_product, delete_product
from .orders import (
    create_order,
    get_order_by_id,
    update_order_items,
    update_order_status,
    delete_order,
    list_orders_by_customer,
    list_orders_by_date_range,
    top_selling_products,
    OutOfStockError,
)
from .customers import create_customer, get_customer_by_id, update_customer, delete_customer

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

class CustomerUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

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

class OrderUpdate(BaseModel):
    items: List[OrderItemIn]

class OrderStatusUpdate(BaseModel):
    status: str

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

class OrderSummaryOut(BaseModel):
    id: int
    customer_id: int
    status: str
    total_cents: int
    created_at: datetime
    updated_at: datetime

class TopProductOut(BaseModel):
    product_id: int
    sku: str
    name: str
    total_quantity: int
    total_sales_cents: int




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

@app.put("/customers/{customer_id}", response_model=CustomerOut)
def update_customer_endpoint(customer_id: int, payload: CustomerUpdate):
    conn = get_conn()
    try:
        row = update_customer(conn, customer_id, payload.email, payload.first_name, payload.last_name, payload.phone)
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        return row
    except UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    finally:
        conn.close()

@app.delete("/customers/{customer_id}", status_code=204)
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

@app.delete("/products/{product_id}", status_code=204)
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
        except ValueError as e:
            if str(e).startswith("PRODUCT_INACTIVE:"):
                pid = str(e).split(":")[1]
                raise HTTPException(status_code=409, detail=f"Product inactive: {pid}")
            raise HTTPException(status_code=400, detail=str(e))
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

@app.put("/orders/{order_id}", response_model=OrderOut)
def update_order_endpoint(order_id: int, payload: OrderUpdate):
    conn = get_conn()
    try:
        order = update_order_items(conn, order_id, [i.model_dump() for i in payload.items])
        return order
    except OutOfStockError as e:
        raise HTTPException(
            status_code=409,
            detail={"code": "OUT_OF_STOCK", "product_id": e.product_id, "available": e.available, "requested": e.requested},
        )
    except KeyError as e:
        msg = str(e)
        if msg == "'ORDER_NOT_FOUND'":
            raise HTTPException(status_code=404, detail="Order not found")
        if msg.startswith("'PRODUCT_NOT_FOUND:"):
            pid = msg.split(":")[1].strip("'")
            raise HTTPException(status_code=404, detail=f"Product not found: {pid}")
        raise
    except ValueError as e:
        if str(e) == "ORDER_NOT_PENDING":
            raise HTTPException(status_code=409, detail="Order must be PENDING to edit")
        if str(e).startswith("PRODUCT_INACTIVE:"):
            pid = str(e).split(":")[1]
            raise HTTPException(status_code=409, detail=f"Product inactive: {pid}")
        raise
    finally:
        conn.close()

@app.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status_endpoint(order_id: int, payload: OrderStatusUpdate):
    conn = get_conn()
    try:
        order = update_order_status(conn, order_id, payload.status)
        return order
    except KeyError as e:
        if str(e) == "'ORDER_NOT_FOUND'":
            raise HTTPException(status_code=404, detail="Order not found")
        raise
    except ValueError as e:
        if str(e) == "INVALID_STATUS":
            raise HTTPException(status_code=400, detail="Invalid status")
        if str(e) == "INVALID_STATUS_TRANSITION":
            raise HTTPException(status_code=409, detail="Invalid status transition")
        raise
    finally:
        conn.close()

@app.delete("/orders/{order_id}", status_code=204)
def delete_order_endpoint(order_id: int):
    conn = get_conn()
    try:
        deleted = delete_order(conn, order_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Order not found")
    except ValueError as e:
        if str(e) == "ORDER_NOT_PENDING":
            raise HTTPException(status_code=409, detail="Only PENDING orders can be deleted")
        raise
    finally:
        conn.close()

@app.get("/customers/{customer_id}/orders", response_model=List[OrderSummaryOut])
def list_customer_orders_endpoint(customer_id: int):
    conn = get_conn()
    try:
        return list_orders_by_customer(conn, customer_id)
    finally:
        conn.close()

@app.get("/orders", response_model=List[OrderSummaryOut])
def list_orders_by_date_endpoint(
    start: datetime = Query(..., description="Start datetime (inclusive)"),
    end: datetime = Query(..., description="End datetime (inclusive)"),
):
    conn = get_conn()
    try:
        return list_orders_by_date_range(conn, start, end)
    finally:
        conn.close()

@app.get("/reports/top-products", response_model=List[TopProductOut])
def top_products_report_endpoint(
    start: datetime = Query(..., description="Start datetime (inclusive)"),
    end: datetime = Query(..., description="End datetime (inclusive)"),
    limit: int = Query(10, ge=1, le=100),
):
    conn = get_conn()
    try:
        return top_selling_products(conn, start, end, limit)
    finally:
        conn.close()

    
