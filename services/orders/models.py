from datetime import datetime
from typing import List

from pydantic import BaseModel


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
