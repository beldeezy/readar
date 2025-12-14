"""Test that the FastAPI app can be imported and /health endpoint works."""
from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint():
    """Test that GET /health returns 200 and {"status": "ok"}."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

