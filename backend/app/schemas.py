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
