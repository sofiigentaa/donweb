from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import routers
from app.database import Base, get_db
from app.main import app
from app.models import Customer, CustomerOrder, OrderItem, Product
from app.routers import _build_ai_context


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()

    customer = Customer(name="Paula Méndez")
    blocks = Product(
        sku="BL-04",
        name="Bloques de construcción",
        price=Decimal("32000.00"),
        stock_quantity=2,
    )
    microscope = Product(
        sku="MI-06",
        name="Microscopio de juguete",
        price=Decimal("26900.00"),
        stock_quantity=2,
    )
    order = CustomerOrder(
        order_number="J-0156",
        customer=customer,
        status="conf",
        total=Decimal("12900.00"),
    )
    order.items.append(OrderItem(product=blocks, quantity=1, unit_price=blocks.price))
    session.add_all([blocks, microscope, order])
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_context_finds_product_by_sku(db):
    facts = _build_ai_context(db, "¿Cuánto stock hay del SKU BL-04?")
    assert any("SKU BL-04" in fact and "stock 2" in fact for fact in facts)


def test_context_finds_order(db):
    facts = _build_ai_context(db, "¿Cómo está el pedido J-0156?")
    assert any("Pedido J-0156" in fact and "Paula Méndez" in fact for fact in facts)


def test_context_finds_product_by_name(db):
    facts = _build_ai_context(db, "¿Cuánto sale el microscopio?")
    assert any("SKU MI-06" in fact for fact in facts)


def test_context_falls_back_to_catalog(db):
    facts = _build_ai_context(db, "Hola, ¿qué productos tienen?")
    assert any("SKU BL-04" in fact for fact in facts)
    assert any("SKU MI-06" in fact for fact in facts)


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


def _fake_llm(monkeypatch, content="Hay 2 unidades disponibles.", fail=False):
    captured = {"calls": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None, **kwargs):
            captured["calls"] += 1
            captured["payload"] = json
            captured["headers"] = headers
            if fail:
                raise routers.httpx.ConnectError("sin conexión")
            return FakeResponse(content)

    monkeypatch.setattr(routers.httpx, "Client", FakeClient)
    return captured


def _chat(db, messages, assistant="atencion"):
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            return client.post(
                "/api/v1/assistant/chat",
                json={"messages": messages, "assistant": assistant},
            )
    finally:
        app.dependency_overrides.clear()


def test_chat_uses_real_db_data(db, monkeypatch):
    captured = _fake_llm(monkeypatch)
    response = _chat(
        db, [{"role": "user", "content": "¿Qué me recomendás del SKU BL-04 para regalar?"}], "stock"
    )
    assert response.status_code == 200
    assert response.json() == {"reply": "Hay 2 unidades disponibles."}
    system_prompt = captured["payload"]["messages"][0]["content"]
    assert "SKU BL-04" in system_prompt
    assert "stock 2 unidades" in system_prompt
    assert "Controlás precios y unidades" in system_prompt


def test_direct_stock_answer_skips_llm(db, monkeypatch):
    captured = _fake_llm(monkeypatch)
    response = _chat(db, [{"role": "user", "content": "Stock del SKU BL-04"}])
    assert "2 unidades en stock" in response.json()["reply"]
    assert captured["calls"] == 0


def test_old_messages_do_not_hijack_new_question(db, monkeypatch):
    captured = _fake_llm(monkeypatch, content="¡De nada!")
    response = _chat(db, [
        {"role": "user", "content": "Stock del SKU BL-04"},
        {"role": "assistant", "content": "El Bloques tiene 2 unidades en stock."},
        {"role": "user", "content": "Gracias, ¿hay algo más que necesite saber?"},
    ])
    assert response.json() == {"reply": "¡De nada!"}
    assert captured["calls"] == 1


def test_follow_up_question_keeps_context(db, monkeypatch):
    captured = _fake_llm(monkeypatch, content="Cuesta $26.900.")
    _chat(db, [
        {"role": "user", "content": "¿Tienen microscopio?"},
        {"role": "assistant", "content": "Sí, tenemos."},
        {"role": "user", "content": "¿Y para qué edad es?"},
    ])
    assert "SKU MI-06" in captured["payload"]["messages"][0]["content"]


def test_search_ignores_accents(db):
    facts = _build_ai_context(db, "tienen bloques de construccion?")
    assert any("SKU BL-04" in fact for fact in facts)


def test_low_stock_query(db):
    facts = _build_ai_context(db, "¿Qué productos tienen poco stock?")
    assert any("poco stock" in fact for fact in facts)
    assert any("SKU BL-04" in fact for fact in facts)


def test_budget_filter(db):
    facts = _build_ai_context(db, "Busco un regalo hasta $30.000")
    assert any("SKU MI-06" in fact for fact in facts)
    assert not any("SKU BL-04" in fact for fact in facts)


def test_falls_back_to_real_data_when_llm_is_down(db, monkeypatch):
    _fake_llm(monkeypatch, fail=True)
    response = _chat(db, [{"role": "user", "content": "¿Tienen microscopio?"}])
    assert response.status_code == 200
    reply = response.json()["reply"]
    assert "Microscopio de juguete" in reply and "SKU MI-06" in reply


def test_sends_api_key_and_model_when_configured(db, monkeypatch):
    captured = _fake_llm(monkeypatch)
    monkeypatch.setattr(routers.settings, "llm_api_key", "clave-test")
    monkeypatch.setattr(routers.settings, "llm_model", "modelo-test")
    _chat(db, [{"role": "user", "content": "¿Tienen microscopio?"}])
    assert captured["headers"] == {"Authorization": "Bearer clave-test"}
    assert captured["payload"]["model"] == "modelo-test"


def test_strips_reasoning_tags(db, monkeypatch):
    _fake_llm(monkeypatch, content="<think>pensando...</think>Sí, tenemos microscopio.")
    response = _chat(db, [{"role": "user", "content": "¿Tienen microscopio?"}])
    assert response.json() == {"reply": "Sí, tenemos microscopio."}
