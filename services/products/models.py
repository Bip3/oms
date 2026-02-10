from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
