from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decimal import Decimal

from sqlalchemy import func, text

from app.database import get_db
from app.models import (
    Customer, CustomerOrder, OrderItem, Product, Seller, StockMovement, Task,
)
from app.schemas import (
    CustomerCreate, CustomerRead, OrderCreate, OrderRead,
    ProductCreate, ProductRead, TaskCreate, TaskRead,
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


# ---------- Orders ----------


def _order_to_dict(order: CustomerOrder) -> dict:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer.name,
        "seller_name": order.seller.name if order.seller else None,
        "status": order.status,
        "fulfillment": order.fulfillment,
        "availability": order.availability,
        "payment_status": order.payment_status,
        "origin": order.origin,
        "gift_wrap": order.gift_wrap,
        "notes": order.notes,
        "total": order.total,
        "created_at": order.created_at,
        "items": [
            {
                "sku": item.product.sku,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.unit_price * item.quantity,
            }
            for item in order.items
        ],
    }


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED, tags=["orders"])
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    # Serializa la generación de order_number entre requests concurrentes.
    db.execute(text("SELECT pg_advisory_xact_lock(42)"))

    # Idempotencia: si el cliente envía un número y ya existe, devolverlo tal cual.
    if payload.order_number:
        existing = db.scalar(
            select(CustomerOrder).where(CustomerOrder.order_number == payload.order_number)
        )
        if existing:
            return _order_to_dict(existing)

    # 1) Resolver productos y validar stock
    products: dict[str, Product] = {}
    for item in payload.items:
        prod = db.scalar(select(Product).where(Product.sku == item.sku, Product.active.is_(True)))
        if not prod:
            raise HTTPException(status_code=404, detail=f"Producto no encontrado: {item.sku}")
        if prod.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Stock insuficiente de {item.sku}: "
                    f"hay {prod.stock_quantity}, se piden {item.quantity}"
                ),
            )
        products[item.sku] = prod

    # 2) Resolver o crear cliente
    customer = db.scalar(
        select(Customer).where(Customer.name == payload.customer_name, Customer.active.is_(True))
    )
    if not customer:
        customer = Customer(name=payload.customer_name, phone=payload.customer_phone)
        db.add(customer)
        db.flush()

    # 3) Resolver o crear vendedor (opcional)
    seller = None
    if payload.seller_name:
        seller = db.scalar(select(Seller).where(Seller.name == payload.seller_name))
        if not seller:
            seller = Seller(name=payload.seller_name)
            db.add(seller)
            db.flush()

    # 4) Resolver order_number (provisto por el cliente o generado secuencialmente)
    if payload.order_number:
        order_number = payload.order_number
    else:
        last_number = db.execute(select(func.max(CustomerOrder.order_number))).scalar()
        next_n = 1
        if last_number and last_number.startswith("J-"):
            try:
                next_n = int(last_number[2:]) + 1
            except ValueError:
                pass
        order_number = f"J-{next_n:04d}"

    # 5) Total desde precios reales de la DB
    total = sum(
        (products[i.sku].price * i.quantity for i in payload.items),
        start=Decimal("0.00"),
    )

    # 6) Crear el pedido
    order = CustomerOrder(
        order_number=order_number,
        customer_id=customer.id,
        seller_id=seller.id if seller else None,
        status=payload.status,
        fulfillment=payload.fulfillment,
        availability=payload.availability,
        payment_status=payload.payment_status,
        origin=payload.origin,
        gift_wrap=payload.gift_wrap,
        notes=payload.notes,
        total=total,
    )
    db.add(order)
    db.flush()

    # 7) Items + descuento de stock + movimiento de stock
    for item in payload.items:
        prod = products[item.sku]
        db.add(OrderItem(
            order_id=order.id,
            product_id=prod.id,
            quantity=item.quantity,
            unit_price=prod.price,
        ))
        prod.stock_quantity -= item.quantity
        db.add(StockMovement(
            product_id=prod.id,
            quantity_delta=-item.quantity,
            reason="order",
            reference=order_number,
        ))

    db.commit()
    db.refresh(order)
    return _order_to_dict(order)


@router.get("/orders", response_model=list[OrderRead], tags=["orders"])
def list_orders(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    statement = (
        select(CustomerOrder)
        .order_by(CustomerOrder.created_at.desc())
        .limit(limit)
    )
    rows = db.scalars(statement).unique().all()
    return [_order_to_dict(o) for o in rows]


@router.get("/orders/{order_number}", response_model=OrderRead, tags=["orders"])
def get_order(order_number: str, db: Session = Depends(get_db)):
    order = db.scalar(
        select(CustomerOrder).where(CustomerOrder.order_number == order_number)
    )
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido no encontrado: {order_number}")
    return _order_to_dict(order)
