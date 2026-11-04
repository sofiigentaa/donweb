"""Carga los datos semilla del panel (9 productos) en PostgreSQL.

Uso:
    cd ~/donweb/backend
    source .venv/bin/activate
    python -m seed
"""
from decimal import Decimal

from app.database import SessionLocal
from app.models import Product, Seller
from app.routers import create_order
from app.schemas import OrderCreate, OrderItemCreate


PRODUCTS = [
    {"sku": "KC-08", "name": "Kit de ciencia Pequeños Químicos", "min_age": 8,  "price": Decimal("27500.00"), "stock_quantity": 4,  "reserved_quantity": 1, "stock_trust": "al día", "color": "#3b78ec"},
    {"sku": "MI-06", "name": "Microscopio de juguete",           "min_age": 6,  "price": Decimal("26900.00"), "stock_quantity": 2,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#1a9e52"},
    {"sku": "PU-00", "name": "Peluche de unicornio",             "min_age": 0,  "price": Decimal("15900.00"), "stock_quantity": 0,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#ff6f9f"},
    {"sku": "RC-10", "name": "Rompecabezas 500 piezas",          "min_age": 10, "price": Decimal("18000.00"), "stock_quantity": 12, "reserved_quantity": 0, "stock_trust": "manual", "color": "#9460ee"},
    {"sku": "BL-04", "name": "Bloques de construcción 120 piezas","min_age": 4, "price": Decimal("32000.00"), "stock_quantity": 3,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#f2b21e"},
    {"sku": "MA-03", "name": "Muñeca articulada",                "min_age": 3,  "price": Decimal("24500.00"), "stock_quantity": 1,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#ea4747"},
    {"sku": "CM-02", "name": "Caballito mecedora de madera",     "min_age": 2,  "price": Decimal("89000.00"), "stock_quantity": 2,  "reserved_quantity": 0, "stock_trust": "manual", "color": "#d6873f"},
    {"sku": "PA-05", "name": "Pista de autos",                   "min_age": 5,  "price": Decimal("45000.00"), "stock_quantity": 5,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#f3843a"},
    {"sku": "JT-03", "name": "Juego de té",                      "min_age": 3,  "price": Decimal("12900.00"), "stock_quantity": 7,  "reserved_quantity": 0, "stock_trust": "al día", "color": "#16a3a3"},
]


SELLERS = [
    {"name": "Sofi", "email": "sofi@sofige.online"},
    {"name": "Nico", "email": "nico@sofige.online"},
]

# Los 5 pedidos del panel original (J-0140 → J-0144). Si ya existen, se omiten.
DEMO_ORDERS = [
    {"order_number": "J-0140", "customer_name": "Ana Torres",
     "items": [("BL-04", 1)], "fulfillment": "pickup", "status": "entr",
     "availability": "confloc", "payment_status": "acred", "origin": "wa",
     "gift_wrap": False, "notes": None, "seller_name": "Nico"},
    {"order_number": "J-0141", "customer_name": "Laura Gómez",
     "items": [("MA-03", 1)], "fulfillment": "pickup", "status": "listo",
     "availability": "confloc", "payment_status": "acred", "origin": "wa",
     "gift_wrap": True, "notes": "17 h", "seller_name": "Sofi"},
    {"order_number": "J-0142", "customer_name": "Martín Ruiz",
     "items": [("KC-08", 1)], "fulfillment": "pickup", "status": "conf",
     "availability": "reserv", "payment_status": "sinpagar", "origin": "wa",
     "gift_wrap": False, "notes": None, "seller_name": "Sofi"},
    {"order_number": "J-0143", "customer_name": "Carla Pérez",
     "items": [("PA-05", 1), ("JT-03", 1)], "fulfillment": "ship",
     "status": "prep", "availability": "confloc", "payment_status": "comprob",
     "origin": "wa", "gift_wrap": False, "notes": None, "seller_name": "Nico"},
    {"order_number": "J-0144", "customer_name": "Rubén Díaz",
     "items": [("RC-10", 2)], "fulfillment": "pickup", "status": "pend",
     "availability": "sinver", "payment_status": "sinpagar", "origin": "phone",
     "gift_wrap": False, "notes": None, "seller_name": None},
]


def main() -> None:
    db = SessionLocal()
    try:
        existing = {p.sku for p in db.query(Product).all()}
        added = 0
        for item in PRODUCTS:
            if item["sku"] in existing:
                continue
            db.add(Product(**item))
            added += 1
        existing_sellers = {x.name for x in db.query(Seller).all()}
        added_s = 0
        for item in SELLERS:
            if item["name"] in existing_sellers:
                continue
            db.add(Seller(**item))
            added_s += 1

        db.commit()
        print(f"Productos: {added} nuevos, {len(PRODUCTS) - added} ya existían (total {len(PRODUCTS)})")
        print(f"Vendedores: {added_s} nuevos, {len(SELLERS) - added_s} ya existían (total {len(SELLERS)})")

        # Seed de pedidos demo
        added_o = 0
        from app.models import CustomerOrder
        existing_orders = {
            r[0] for r in db.query(CustomerOrder.order_number).all()
        }
        for demo in DEMO_ORDERS:
            if demo["order_number"] in existing_orders:
                continue
            payload = OrderCreate(
                order_number=demo["order_number"],
                customer_name=demo["customer_name"],
                items=[OrderItemCreate(sku=sku, quantity=qty) for sku, qty in demo["items"]],
                fulfillment=demo["fulfillment"],
                status=demo["status"],
                availability=demo["availability"],
                payment_status=demo["payment_status"],
                origin=demo["origin"],
                gift_wrap=demo["gift_wrap"],
                notes=demo["notes"],
                seller_name=demo["seller_name"],
            )
            create_order(payload, db)
            added_o += 1
        print(f"Pedidos demo: {added_o} nuevos, {len(DEMO_ORDERS) - added_o} ya existían (total {len(DEMO_ORDERS)})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
