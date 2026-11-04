from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CustomerRead(CustomerCreate):
    id: int
    active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    stock_quantity: int = Field(default=0, ge=0)
    photo_url: str | None = Field(default=None, max_length=1000)
    min_age: int | None = Field(default=None, ge=0, le=18)
    stock_trust: str = Field(default="al día", pattern="^(al día|manual)$")
    color: str | None = Field(default=None, max_length=20)


class ProductRead(ProductCreate):
    id: int
    reserved_quantity: int
    active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=220)
    description: str | None = None
    assistant: str = Field(default="local", max_length=30)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    due_at: datetime | None = None


class TaskRead(TaskCreate):
    id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class OrderItemCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=60)
    quantity: int = Field(ge=1, le=999)


class OrderCreate(BaseModel):
    order_number: str | None = Field(default=None, max_length=40, pattern=r"^[A-Z]-\d{3,6}$")
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: str | None = Field(default=None, max_length=40)
    items: list[OrderItemCreate] = Field(min_length=1)
    fulfillment: str = Field(default="pickup", pattern="^(pickup|ship)$")
    status: str = Field(default="pend", pattern="^(pend|conf|prep|listo|entr|canc)$")
    availability: str | None = Field(default=None, pattern="^(sinver|reserv|confloc|sinstock)$")
    payment_status: str | None = Field(default=None, pattern="^(sinpagar|comprob|acred)$")
    origin: str | None = Field(default=None, pattern="^(wa|phone|web)$")
    gift_wrap: bool = False
    notes: str | None = None
    seller_name: str | None = Field(default=None, max_length=160)


class OrderItemRead(BaseModel):
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderRead(BaseModel):
    id: int
    order_number: str
    customer_name: str
    seller_name: str | None
    status: str
    fulfillment: str
    availability: str | None
    payment_status: str | None
    origin: str | None
    gift_wrap: bool
    notes: str | None
    total: Decimal
    created_at: datetime
    items: list[OrderItemRead]


class ActivityLogCreate(BaseModel):
    actor_type: str = Field(min_length=2, max_length=30)
    action: str = Field(max_length=100)
    entity_type: str = Field(default="activity", max_length=60)
    details: str | None = None

class ActivityLogRead(ActivityLogCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
