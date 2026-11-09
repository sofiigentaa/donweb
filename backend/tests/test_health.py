from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_serves_panel():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_backend_files_are_not_exposed():
    assert client.get("/.env").status_code == 404
    assert client.get("/README.md").status_code == 404


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
