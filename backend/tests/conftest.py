from collections.abc import Generator
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

# Isolate route-level service instantiation from real external API keys during test collection
with patch("backend.app.services.vector_store.EmbeddingService"), \
     patch("backend.app.services.rag_service.LLMService"):
    from backend.app.main import app


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient instance for integration tests."""
    with TestClient(app) as test_client:
        yield test_client
