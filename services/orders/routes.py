from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Query

from shared.db import get_conn

from .models import (
    OrderCreate,
    OrderOut,
    OrderStatusUpdate,
    OrderSummaryOut,
    OrderUpdate,
    TopProductOut,
)
from .service import (
    OutOfStockError,
    create_order,
    delete_order,
    get_order_by_id,
    list_orders_by_customer,
    list_orders_by_date_range,
    top_selling_products,
    update_order_items,
    update_order_status,
)

router = APIRouter()


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order_endpoint(payload: OrderCreate):
    conn = get_conn()
    try:
        try:
            order = create_order(conn, payload.customer_id, [i.model_dump() for i in payload.items])
            return order
        except OutOfStockError as e:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OUT_OF_STOCK",
                    "product_id": e.product_id,
                    "available": e.available,
                    "requested": e.requested,
                },
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


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order_endpoint(order_id: int):
    conn = get_conn()
    try:
        order = get_order_by_id(conn, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return order
    finally:
        conn.close()


@router.put("/orders/{order_id}", response_model=OrderOut)
def update_order_endpoint(order_id: int, payload: OrderUpdate):
    conn = get_conn()
    try:
        order = update_order_items(conn, order_id, [i.model_dump() for i in payload.items])
        return order
    except OutOfStockError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "OUT_OF_STOCK",
                "product_id": e.product_id,
                "available": e.available,
                "requested": e.requested,
            },
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


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
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


@router.delete("/orders/{order_id}", status_code=204)
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


@router.get("/customers/{customer_id}/orders", response_model=List[OrderSummaryOut])
def list_customer_orders_endpoint(customer_id: int):
    conn = get_conn()
    try:
        return list_orders_by_customer(conn, customer_id)
    finally:
        conn.close()


@router.get("/orders", response_model=List[OrderSummaryOut])
def list_orders_by_date_endpoint(
    start: datetime = Query(..., description="Start datetime (inclusive)"),
    end: datetime = Query(..., description="End datetime (inclusive)"),
):
    conn = get_conn()
    try:
        return list_orders_by_date_range(conn, start, end)
    finally:
        conn.close()


@router.get("/reports/top-products", response_model=List[TopProductOut])
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
