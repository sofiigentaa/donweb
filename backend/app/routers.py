from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decimal import Decimal

from sqlalchemy import func, text

import logging
import re
import unicodedata

import httpx
from app.config import settings
from app.database import get_db
from app.models import (
    ActivityLog, Customer, CustomerOrder, OrderItem, Product, Seller, StockMovement, Task,
)
from app.schemas import (
    ActivityLogCreate, ActivityLogRead, ChatRequest, ChatResponse, TaskUpdate,
    CustomerCreate, CustomerRead, OrderCreate, OrderRead,
    ProductCreate, ProductRead, SellerRead, TaskCreate, TaskRead,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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

    # 3) Resolver o crear vendedor (Reparto Equitativo / Load Balancing)
    seller = None
    if payload.seller_name:
        seller = db.scalar(select(Seller).where(Seller.name == payload.seller_name))
    else:
        # Balanceo de carga: buscar al vendedor con menos tareas pendientes
        sellers = db.scalars(select(Seller).where(Seller.active.is_(True))).all()
        if sellers:
            loads = []
            for sel in sellers:
                # Contar cuántas tareas pendientes tiene
                task_count = db.scalar(
                    select(func.count(Task.id)).where(
                        Task.assistant == "vendedores",
                        Task.status != "done",
                        Task.title.like(f"{sel.name}:%")
                    )
                )
                loads.append((sel, task_count))
            # Ordenar por cantidad de tareas (ascendente)
            loads.sort(key=lambda x: x[1])
            seller = loads[0][0]

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

    # 6.5) Crear tarea automática para el vendedor asignado
    if seller:
        task = Task(
            title=f"{seller.name}: Preparar un pedido",
            description=order_number,
            assistant="vendedores",
            priority="normal",
            status="pending"
        )
        db.add(task)

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


# ---------- Activity Logs ----------


@router.get("/activity-logs", response_model=list[ActivityLogRead], tags=["activity"])
def list_activity_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    return db.scalars(statement).all()


@router.post("/activity-logs", response_model=ActivityLogRead, status_code=status.HTTP_201_CREATED, tags=["activity"])
def create_activity_log(payload: ActivityLogCreate, db: Session = Depends(get_db)):
    log = ActivityLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ---------- IA (modelo compatible con la API de OpenAI: llama.cpp, Groq, OpenRouter...) ----------

_SKU_RE = re.compile(r"\b[A-Za-z]{2,4}-\d{2,4}\b")
_ORDER_RE = re.compile(r"\b[Jj]-\d{3,6}\b")
_AGE_RE = re.compile(r"\b(\d{1,2})\s*(?:años|anos|año|ano)\b")
_BUDGET_RE = re.compile(
    r"(?:hasta|menos de|m[aá]ximo|presupuesto(?: de)?|no m[aá]s de)\s*\$?\s*([\d][\d\.,]*)\s*(mil|k)?",
)
_STOPWORDS = {
    "stock", "precio", "precios", "tienen", "tenes", "producto", "productos", "cuanto",
    "cuanta", "cuantos", "cuantas", "hay", "del", "los", "las", "una", "unos", "unas",
    "para", "sobre", "quiero", "necesito", "sale", "salen", "cuesta", "cuestan", "vale",
    "valen", "costo", "hola", "buenas", "busco", "tenemos", "algun", "alguna", "algo",
    "regalo", "regalar", "nene", "nena", "chico", "chica", "anos", "hasta", "menos",
    "mas", "pesos", "queda", "quedan", "unidades", "disponible", "disponibles", "como",
    "esta", "estan", "favor", "gracias", "recomendas", "recomendame", "mostrame",
}
_STOCK_WORDS = ("stock", "unidad", "unidades", "disponible", "quedan", "queda")
_PRICE_WORDS = ("precio", "cuanto sale", "cuanto cuesta", "cuesta", "vale", "costo")
_CATALOG_WORDS = (
    "producto", "productos", "tienen", "tenes", "catalogo", "juguete", "juguetes",
    "recomend", "regalo", "regalar", "busco", "stock", "precio", "sale", "cuesta",
)
_LOW_STOCK_WORDS = ("poco stock", "sin stock", "agotad", "reponer", "bajo stock", "se acaba", "faltan")
_PENDING_WORDS = ("pendiente", "pedidos de hoy", "ultimos pedidos", "pedidos abiertos", "por preparar", "en preparacion")
_ACTIVE_ORDER_STATUSES = ("pend", "pending", "conf", "prep", "listo")

_ORDER_STATUS = {
    "pend": "pendiente de confirmar",
    "pending": "pendiente de confirmar",
    "conf": "confirmado",
    "prep": "en preparación",
    "listo": "listo",
    "entr": "entregado",
    "canc": "cancelado",
}

_ASSISTANT_ROLES = {
    "atencion": "Atendés a clientes de la juguetería: recomendás juguetes según edad y presupuesto, "
                "informás precios y disponibilidad, y si el cliente lo pide lo derivás a una persona del local.",
    "pedidos": "Ayudás a armar pedidos: confirmás productos y cantidades, mostrás el total y "
               "pedís confirmación antes de cerrar. Informás el estado de pedidos existentes.",
    "stock": "Controlás precios y unidades: informás stock disponible, avisás qué productos "
             "tienen poco stock o hay que reponer.",
    "local": "Coordinás al equipo del local: pedidos pendientes, qué hay que preparar y quién se encarga.",
    "vendedores": "Coordinás a los vendedores: qué pedidos tienen que preparar o atender y su avance.",
}


def _normalize(text: str) -> str:
    """Minúsculas y sin tildes, para comparar 'muñeca' con 'muneca'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _has_any(normalized: str, words: tuple[str, ...]) -> bool:
    return any(word in normalized for word in words)


def _money(value: Decimal) -> str:
    return "$" + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".").removesuffix(",00")


def _available(prod: Product) -> int:
    return max(prod.stock_quantity - (prod.reserved_quantity or 0), 0)


def _product_fact(prod: Product) -> str:
    fact = (
        f"SKU {prod.sku}: {prod.name}, stock {prod.stock_quantity} unidades, "
        f"precio {_money(prod.price)}"
    )
    if prod.reserved_quantity:
        fact += f", {prod.reserved_quantity} reservadas ({_available(prod)} disponibles para vender)"
    if prod.min_age is not None:
        fact += f", desde {prod.min_age} años"
    if prod.stock_trust and prod.stock_trust != "al día":
        fact += f", stock {prod.stock_trust} (confirmar con el local)"
    return fact + "."


def _order_fact(order: CustomerOrder) -> str:
    items = ", ".join(f"{item.quantity}x {item.product.name}" for item in order.items)
    seller = order.seller.name if order.seller else "sin vendedor"
    status = _ORDER_STATUS.get(order.status, order.status)
    return (
        f"Pedido {order.order_number}: cliente {order.customer.name}, vendedor {seller}, "
        f"estado {status}, total {_money(order.total)}, items: {items or 'sin items'}."
    )


def _parse_budget(normalized: str) -> Decimal | None:
    match = _BUDGET_RE.search(normalized)
    if not match:
        return None
    digits = re.sub(r"[.,]", "", match.group(1))
    if not digits:
        return None
    amount = Decimal(digits)
    if match.group(2):
        amount *= 1000
    return amount


def _search_products(db: Session, normalized: str) -> list[Product]:
    """Busca productos por nombre ignorando tildes y plurales simples."""
    tokens = [
        token for token in re.findall(r"[a-z0-9]{4,}", normalized)
        if token not in _STOPWORDS and not token.isdigit()
    ]
    if not tokens:
        return []
    stems = {token[:-1] if token.endswith("s") else token for token in tokens}
    scored = []
    for prod in db.scalars(select(Product).where(Product.active.is_(True))).all():
        haystack = _normalize(f"{prod.name} {prod.description or ''}")
        score = sum(1 for stem in stems if stem in haystack)
        if score:
            scored.append((-score, prod.name, prod))
    scored.sort(key=lambda item: item[:2])
    return [prod for *_, prod in scored[:8]]


def _build_ai_context(db: Session, text: str) -> list[str]:
    """Busca en la base los datos reales que el usuario está consultando."""
    facts: list[str] = []
    normalized = _normalize(text)

    for number in sorted({m.upper() for m in _ORDER_RE.findall(text)}):
        order = db.scalar(
            select(CustomerOrder).where(func.upper(CustomerOrder.order_number) == number)
        )
        facts.append(_order_fact(order) if order else f"No existe un pedido {number}.")

    skus = sorted({m.upper() for m in _SKU_RE.findall(text)} - {n.upper() for n in _ORDER_RE.findall(text)})
    for sku in skus:
        prod = db.scalar(select(Product).where(func.upper(Product.sku) == sku))
        facts.append(_product_fact(prod) if prod else f"No existe un producto con SKU {sku}.")

    if _has_any(normalized, _LOW_STOCK_WORDS):
        low = db.scalars(
            select(Product)
            .where(Product.active.is_(True), Product.stock_quantity - Product.reserved_quantity <= 3)
            .order_by(Product.stock_quantity, Product.name)
            .limit(10)
        ).all()
        facts.append("Productos con poco stock (3 o menos disponibles):" if low else "No hay productos con poco stock.")
        facts.extend(_product_fact(prod) for prod in low)

    if _has_any(normalized, _PENDING_WORDS):
        orders = db.scalars(
            select(CustomerOrder)
            .where(CustomerOrder.status.in_(_ACTIVE_ORDER_STATUSES))
            .order_by(CustomerOrder.created_at.desc())
            .limit(10)
        ).all()
        facts.append(f"Pedidos abiertos: {len(orders)}." if orders else "No hay pedidos abiertos.")
        facts.extend(_order_fact(order) for order in orders)

    age_match = _AGE_RE.search(normalized)
    budget = _parse_budget(normalized)
    wants_catalog = bool(age_match or budget) or _has_any(normalized, _CATALOG_WORDS)

    if not skus and wants_catalog:
        products = _search_products(db, normalized)
        if not products:
            query = select(Product).where(Product.active.is_(True), Product.stock_quantity > 0)
            if age_match:
                age = int(age_match.group(1))
                query = query.where(or_(Product.min_age.is_(None), Product.min_age <= age))
            if budget is not None:
                query = query.where(Product.price <= budget)
            products = db.scalars(query.order_by(Product.name).limit(12)).all()
            if age_match or budget is not None:
                filters = []
                if age_match:
                    filters.append(f"aptos para {age_match.group(1)} años")
                if budget is not None:
                    filters.append(f"hasta {_money(budget)}")
                facts.append(
                    f"Productos {' y '.join(filters)}:" if products
                    else f"No hay productos {' y '.join(filters)} con stock."
                )
        facts.extend(_product_fact(prod) for prod in products)

    return facts


def _direct_reply(db: Session, text: str) -> str | None:
    """Respuestas exactas para consultas simples de stock/precio/pedido.

    Evita que el modelo invente cantidades o precios.
    """
    normalized = _normalize(text)
    order_numbers = {number.upper() for number in _ORDER_RE.findall(text)}
    skus = {sku.upper() for sku in _SKU_RE.findall(text)} - order_numbers

    if len(skus) == 1 and not order_numbers:
        sku = next(iter(skus))
        prod = db.scalar(select(Product).where(func.upper(Product.sku) == sku))
        if not prod:
            return f"No encontré un producto con el SKU {sku}. ¿Lo podés revisar?"
        wants_stock = _has_any(normalized, _STOCK_WORDS) or re.search(r"\bhay\b", normalized)
        wants_price = _has_any(normalized, _PRICE_WORDS)
        stock_text = f"tiene {prod.stock_quantity} unidades en stock"
        if prod.reserved_quantity:
            stock_text += f" ({_available(prod)} disponibles, {prod.reserved_quantity} reservadas)"
        if prod.stock_trust and prod.stock_trust != "al día":
            stock_text += f"; el stock está {prod.stock_trust}, conviene confirmarlo con el local"
        if wants_stock and wants_price:
            return f"El {prod.name} (SKU {prod.sku}) {stock_text} y cuesta {_money(prod.price)}."
        if wants_stock:
            return f"El {prod.name} (SKU {prod.sku}) {stock_text}."
        if wants_price:
            return f"El {prod.name} (SKU {prod.sku}) cuesta {_money(prod.price)}."

    if len(order_numbers) == 1 and not skus:
        number = next(iter(order_numbers))
        order = db.scalar(
            select(CustomerOrder).where(func.upper(CustomerOrder.order_number) == number)
        )
        if not order:
            return f"No encontré el pedido {number}. ¿Me confirmás el número?"
        items = ", ".join(f"{item.quantity}x {item.product.name}" for item in order.items)
        status = _ORDER_STATUS.get(order.status, order.status)
        return (
            f"El pedido {order.order_number} de {order.customer.name} está {status}, "
            f"por un total de {_money(order.total)}"
            + (f", con {items}." if items else ".")
        )

    return None


def _facts_fallback(facts: list[str]) -> str:
    """Respuesta armada solo con datos reales cuando el modelo no está disponible."""
    shown = facts[:6]
    reply = "Esto es lo que encontré:\n" + "\n".join(f"• {fact}" for fact in shown)
    if len(facts) > len(shown):
        reply += f"\n… y {len(facts) - len(shown)} más."
    return reply


def _clean_reply(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.strip()


def _chat_history(payload: ChatRequest) -> list[dict[str, str]]:
    """Últimos turnos válidos, alternando y empezando por el usuario."""
    history: list[dict[str, str]] = []
    for msg in payload.messages[-10:]:
        role = msg.role if msg.role in ("user", "assistant") else None
        content = (msg.content or "").strip()[:2000]
        if not role or not content:
            continue
        if history and history[-1]["role"] == role:
            history[-1]["content"] += "\n" + content
        else:
            history.append({"role": role, "content": content})
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


@router.post("/assistant/chat", response_model=ChatResponse, tags=["ai"])
def chat_with_ai(payload: ChatRequest, db: Session = Depends(get_db)):
    history = _chat_history(payload)
    user_turns = [msg["content"] for msg in history if msg["role"] == "user"]
    if not user_turns:
        return {"reply": "¡Hola! ¿En qué te puedo ayudar?"}
    last_text = user_turns[-1]

    direct = _direct_reply(db, last_text)
    if direct is not None:
        return {"reply": direct}

    facts = _build_ai_context(db, last_text)
    if not facts and len(user_turns) > 1:
        # Preguntas de seguimiento ("¿y cuánto sale?"): usamos el turno anterior.
        facts = _build_ai_context(db, user_turns[-2])

    role = _ASSISTANT_ROLES.get(payload.assistant, _ASSISTANT_ROLES["atencion"])
    system_prompt = (
        f"Sos el asistente '{payload.assistant}' de la juguetería Caballito y Muñequita. {role}\n"
        "Reglas:\n"
        "- Respondé en español rioplatense, amable y concreto (máximo 4 oraciones o una lista corta).\n"
        "- Usá SOLO los datos reales de abajo para precios, stock, edades y pedidos. "
        "Nunca inventes productos, cantidades, precios ni números de pedido.\n"
        "- Si el dato no está, decilo y pedí el SKU, el nombre del producto o el número de pedido.\n"
        "- Si el stock dice 'confirmar con el local', avisalo."
    )
    if facts:
        system_prompt += (
            "\n\nDATOS REALES DE LA BASE DE DATOS:\n" + "\n".join(f"- {fact}" for fact in facts)
        )
    else:
        system_prompt += "\n\nNo se encontraron datos para esta consulta en la base."

    request_body: dict = {
        "messages": [{"role": "system", "content": system_prompt}, *history[-6:]],
        "temperature": 0.2,
        "max_tokens": 350,
    }
    if settings.llm_model:
        request_body["model"] = settings.llm_model
        if "gpt-oss" in settings.llm_model:
            # Modelo que razona: poco razonamiento alcanza y deja tokens para la respuesta.
            request_body["reasoning_effort"] = "low"
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {}

    try:
        with httpx.Client(timeout=settings.llm_timeout) as client:
            response = client.post(
                f"{settings.llama_base_url.rstrip('/')}/chat/completions",
                json=request_body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        reply = _clean_reply(data["choices"][0]["message"].get("content") or "")
        if reply:
            return {"reply": reply}
    except httpx.TimeoutException:
        logger.warning("El modelo de IA tardó más de %ss", settings.llm_timeout)
    except httpx.HTTPError as exc:
        logger.warning("No se pudo usar el modelo de IA: %s", exc)
    except (KeyError, IndexError, TypeError, ValueError):
        logger.warning("Respuesta inesperada del modelo de IA")

    if facts:
        return {"reply": _facts_fallback(facts)}
    return {
        "reply": "Ahora no puedo procesar consultas abiertas. Pasame el SKU del producto "
                 "o el número de pedido (por ejemplo J-0156) y te doy el dato al instante."
    }


@router.patch("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.scalar(select(Task).where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    task.status = payload.status
    db.commit()
    db.refresh(task)
    return task


@router.get("/sellers", response_model=list[SellerRead], tags=["sellers"])
def list_sellers(db: Session = Depends(get_db)):
    return db.scalars(select(Seller).where(Seller.active.is_(True)).order_by(Seller.name)).all()
