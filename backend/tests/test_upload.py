import io
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.core.exceptions import CorruptedDocumentError, EmptyDocumentError


def test_list_documents_returns_list(client: TestClient) -> None:
    """Verify GET /api/upload returns a list of indexed documents."""
    response = client.get("/api/upload")
    assert response.status_code == 200
    docs = response.json()
    assert isinstance(docs, list)
    if docs:
        first = docs[0]
        assert "name" in first
        assert "type" in first
        assert "category" in first
        assert "status" in first


def test_upload_missing_or_empty_filename_returns_400(client: TestClient) -> None:
    """Verify POST /api/upload with whitespace filename returns 400."""
    response = client.post(
        "/api/upload",
        files={"file": ("   ", io.BytesIO(b"content"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Filename is missing or empty" in response.json()["detail"]


def test_upload_unsupported_file_type_returns_400(client: TestClient) -> None:
    """Verify POST /api/upload rejects unsupported extension with 400."""
    response = client.post(
        "/api/upload",
        files={"file": ("malicious.exe", io.BytesIO(b"content"), "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type '.exe'" in response.json()["detail"]


def test_upload_empty_0_byte_file_returns_400(client: TestClient) -> None:
    """Verify POST /api/upload rejects 0-byte file with 400."""
    response = client.post(
        "/api/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    assert "Uploaded file is empty" in response.json()["detail"]


def test_upload_document_ingestion_error_returns_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify DocumentIngestionError during parsing returns 400."""
    from backend.app.api.routes import upload

    def mock_ingest_fail(*args, **kwargs):
        raise EmptyDocumentError("corrupt.txt", reason="No extractable text")

    monkeypatch.setattr(upload.ingestion_service, "ingest_file", mock_ingest_fail)

    response = client.post(
        "/api/upload",
        files={"file": ("corrupt.txt", io.BytesIO(b"some content"), "text/plain")},
    )
    assert response.status_code == 400
    assert "Empty document error" in response.json()["detail"]


def test_upload_successful_file_returns_200(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify successful document upload returns 200 and expected ingestion payload."""
    from backend.app.api.routes import upload

    mock_result = {
        "filename": "sample_policy.txt",
        "file_type": "txt",
        "pages": 1,
        "chunks": ["chunk1", "chunk2"],
        "stored_chunks": 2,
        "processed": True,
    }

    monkeypatch.setattr(
        upload.ingestion_service,
        "ingest_file",
        lambda *args, **kwargs: mock_result,
    )

    response = client.post(
        "/api/upload",
        files={"file": ("sample_policy.txt", io.BytesIO(b"Policy text content"), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "sample_policy.txt"
    assert data["file_type"] == "txt"
    assert data["pages"] == 1
    assert data["chunks_created"] == 2
    assert data["chunks_stored"] == 2
    assert data["processed"] is True
