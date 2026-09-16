from unittest.mock import MagicMock, patch
import pytest
from backend.app.services.embedding import (
    EmbeddingService,
    is_valid_api_key,
)


class TestApiKeyValidation:
    """Tests for API key presence and placeholder detection."""

    def test_missing_or_empty_keys(self) -> None:
        assert is_valid_api_key(None) is False
        assert is_valid_api_key("") is False
        assert is_valid_api_key("   ") is False

    def test_placeholder_keys(self) -> None:
        assert is_valid_api_key("your-google-api-key-here") is False
        assert is_valid_api_key("YOUR-GOOGLE-API-KEY-HERE") is False
        assert is_valid_api_key("placeholder") is False
        assert is_valid_api_key("changeme") is False
        assert is_valid_api_key("<your-google-api-key-here>") is False

    def test_valid_key_format(self) -> None:
        assert is_valid_api_key("AIzaSyFakeKeyForTesting123456789") is True


class TestEmbeddingServiceOffline:
    """Offline unit tests using mocks to verify EmbeddingService logic."""

    def test_init_raises_when_key_missing_or_placeholder(self) -> None:
        with patch("backend.app.services.embedding.settings.GOOGLE_API_KEY", None):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or set to a placeholder"):
                EmbeddingService(api_key=None)

        with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing or set to a placeholder"):
            EmbeddingService(api_key="your-google-api-key-here")

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_init_success_with_valid_key(self, mock_client_cls: MagicMock) -> None:
        service = EmbeddingService(
            api_key="valid-dummy-key-for-test",
            model="gemini-embedding-001",
            dimension=768,
        )
        assert service.model == "gemini-embedding-001"
        assert service.dimension == 768
        mock_client_cls.assert_called_once_with(
            model="gemini-embedding-001",
            google_api_key="valid-dummy-key-for-test",
            output_dimensionality=768,
        )

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_query_success(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        dummy_vector = [0.1] * 768
        mock_instance.embed_query.return_value = dummy_vector
        mock_client_cls.return_value = mock_instance

        service = EmbeddingService(api_key="valid-dummy-key")
        result = service.embed_query("Sample search query")

        assert len(result) == 768
        assert result == dummy_vector
        mock_instance.embed_query.assert_called_once_with("Sample search query")

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_query_empty_text_raises_error(self, mock_client_cls: MagicMock) -> None:
        service = EmbeddingService(api_key="valid-dummy-key")

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            service.embed_query("")

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            service.embed_query("   ")

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_query_dimension_mismatch_raises_error(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        # Return wrong dimension (e.g. 512 instead of 768)
        mock_instance.embed_query.return_value = [0.1] * 512
        mock_client_cls.return_value = mock_instance

        service = EmbeddingService(api_key="valid-dummy-key", dimension=768)
        with pytest.raises(ValueError, match="Embedding dimension mismatch: expected 768, got 512"):
            service.embed_query("Test query")

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_documents_success(self, mock_client_cls: MagicMock) -> None:
        mock_instance = MagicMock()
        dummy_vectors = [[0.1] * 768, [0.2] * 768]
        mock_instance.embed_documents.return_value = dummy_vectors
        mock_client_cls.return_value = mock_instance

        service = EmbeddingService(api_key="valid-dummy-key")
        docs = ["First document text", "Second document text"]
        results = service.embed_documents(docs)

        assert len(results) == 2
        assert len(results[0]) == 768
        assert len(results[1]) == 768
        mock_instance.embed_documents.assert_called_once_with(docs)

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_documents_empty_list_raises_error(self, mock_client_cls: MagicMock) -> None:
        service = EmbeddingService(api_key="valid-dummy-key")

        with pytest.raises(ValueError, match="Document list cannot be empty"):
            service.embed_documents([])

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_documents_empty_item_raises_error(self, mock_client_cls: MagicMock) -> None:
        service = EmbeddingService(api_key="valid-dummy-key")

        with pytest.raises(ValueError, match="Document at index 1 cannot be empty"):
            service.embed_documents(["Valid document", "   "])

    @patch("backend.app.services.embedding.GoogleGenerativeAIEmbeddings")
    def test_embed_documents_dimension_mismatch_raises_error(
        self, mock_client_cls: MagicMock
    ) -> None:
        mock_instance = MagicMock()
        # Second vector has invalid length
        mock_instance.embed_documents.return_value = [[0.1] * 768, [0.2] * 256]
        mock_client_cls.return_value = mock_instance

        service = EmbeddingService(api_key="valid-dummy-key", dimension=768)
        with pytest.raises(ValueError, match="Document 1 embedding dimension mismatch: expected 768, got 256"):
            service.embed_documents(["Doc 1", "Doc 2"])
