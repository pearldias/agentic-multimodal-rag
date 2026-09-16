from fastapi.testclient import TestClient


def test_health_endpoint_returns_200_and_valid_payload(client: TestClient) -> None:
    """Verify GET /health returns 200 OK and valid health payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    data = response.json()
    assert data == {
        "status": "healthy",
        "version": "0.1.0",
        "environment": "development",
    }
