import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Seller
from app.security import get_password_hash

ADMIN_SECRET = pyotp.random_base32()
SELLER_SECRET = pyotp.random_base32()
NEW_SELLER = {"name": "Nuevo", "email": "nuevo@test.com", "password": "clave1234"}


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add_all([
        Seller(name="Admin", email="admin@test.com", password_hash=get_password_hash("clave1234"),
               totp_secret=ADMIN_SECRET, is_admin=True),
        Seller(name="Vendedora", email="vende@test.com", password_hash=get_password_hash("clave1234"),
               totp_secret=SELLER_SECRET),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()
    db.close()


def _login(client, email, secret):
    return client.post("/api/v1/auth/login", json={
        "email": email, "password": "clave1234", "totp_code": pyotp.TOTP(secret).now(),
    })


def test_create_seller_requires_token(client):
    assert client.post("/api/v1/admin/sellers", json=NEW_SELLER).status_code == 401


def test_create_seller_rejects_invalid_token(client):
    headers = {"Authorization": "Bearer basura"}
    assert client.post("/api/v1/admin/sellers", json=NEW_SELLER, headers=headers).status_code == 401


def test_seller_token_cannot_create_sellers(client):
    token = _login(client, "vende@test.com", SELLER_SECRET).json()["access_token"]
    response = client.post("/api/v1/admin/sellers", json=NEW_SELLER,
                           headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_admin_login_requires_2fa(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "clave1234"})
    assert response.status_code == 401
    assert response.json()["detail"] == "2FA_REQUIRED"
    response = client.post("/api/v1/auth/login",
                           json={"email": "admin@test.com", "password": "clave1234", "totp_code": "000000"})
    assert response.status_code == 401


def test_admin_can_create_seller(client):
    login = _login(client, "admin@test.com", ADMIN_SECRET).json()
    assert login["role"] == "admin"
    response = client.post("/api/v1/admin/sellers", json=NEW_SELLER,
                           headers={"Authorization": f"Bearer {login['access_token']}"})
    assert response.status_code == 200
    assert response.json()["qr_base64"]


def test_admins_are_not_listed_as_sellers(client):
    names = [s["name"] for s in client.get("/api/v1/sellers").json()]
    assert names == ["Vendedora"]
