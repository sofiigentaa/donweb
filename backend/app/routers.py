from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer, Product, Task
from app.schemas import (
    CustomerCreate, CustomerRead, ProductCreate, ProductRead, TaskCreate, TaskRead,
)

router = APIRouter()


@router.get("/customers", response_model=list[CustomerRead], tags=["customers"])
def list_customers(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Customer).where(Customer.active.is_(True)).order_by(Customer.name).limit(limit)
    if q:
        statement = statement.where(Customer.name.ilike(f"%{q}%"))
    return db.scalars(statement).all()


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED, tags=["customers"])
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/products", response_model=list[ProductRead], tags=["stock"])
def list_products(
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    statement = select(Product).where(Product.active.is_(True)).order_by(Product.name).limit(limit)
    if q:
        statement = statement.where(
            Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%")
        )
    return db.scalars(statement).all()


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED, tags=["stock"])
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="El SKU ya existe.") from exc
    db.refresh(product)
    return product


@router.get("/tasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(
    status_filter: str = Query(default="pending", alias="status", pattern="^(pending|in_progress|done|all)$"),
    db: Session = Depends(get_db),
):
    statement = select(Task).order_by(Task.created_at.desc()).limit(200)
    if status_filter != "all":
        statement = statement.where(Task.status == status_filter)
    return db.scalars(statement).all()


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
