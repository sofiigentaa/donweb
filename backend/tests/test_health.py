from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_service_metadata():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "Panel Caballito y Muñequita API"


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
