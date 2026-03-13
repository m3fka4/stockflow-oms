from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import OrderStatus, RoleEnum


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: RoleEnum


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: RoleEnum
    is_active: bool
    created_at: datetime


class ProductCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    price: Decimal = Field(gt=0)
    initial_quantity: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class InventoryUpdate(BaseModel):
    quantity: int = Field(ge=0)
    reserved: int | None = Field(default=None, ge=0)


class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quantity: int
    reserved: int
    updated_at: datetime


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    inventory_item: InventoryRead | None


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=2, max_length=255)
    customer_email: EmailStr
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: OrderStatus | None
    new_status: OrderStatus
    changed_by_id: int | None
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    customer_name: str
    customer_email: EmailStr
    status: OrderStatus
    total_amount: Decimal
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]
    status_history: list[StatusHistoryRead]


class DashboardSummary(BaseModel):
    total_products: int
    active_products: int
    total_orders: int
    pending_orders: int
    completed_orders: int
    low_stock_products: int
    inventory_units: int
    inventory_reserved: int
    revenue_total: Decimal


class LowStockItem(BaseModel):
    product_id: int
    sku: str
    name: str
    quantity: int
    reserved: int


class RealtimeEvent(BaseModel):
    event_type: str
    entity: str
    payload: dict
    created_at: datetime
