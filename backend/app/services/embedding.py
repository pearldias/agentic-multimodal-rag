import logging
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Known placeholder key patterns to guard against accidental non-configured runs
PLACEHOLDER_KEYS = {
    "your-google-api-key-here",
    "your_google_api_key_here",
    "placeholder",
    "<your-google-api-key-here>",
    "your_api_key",
    "changeme",
    "none",
}


def is_valid_api_key(key: str | None) -> bool:
    """Validate that the API key is present, non-empty, and not a known placeholder."""
    if not key or not key.strip():
        return False
    cleaned = key.strip().lower()
    if cleaned in PLACEHOLDER_KEYS or "your-google-api-key" in cleaned or "your_google_api_key" in cleaned:
        return False
    return True


class EmbeddingService:
    """Service for generating vector embeddings via Google Gemini with dimension validation."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ):
        resolved_key = api_key if api_key is not None else settings.GOOGLE_API_KEY
        if not is_valid_api_key(resolved_key):
            raise ValueError(
                "GOOGLE_API_KEY is missing or set to a placeholder. "
                "Please configure a valid GOOGLE_API_KEY in your .env file or environment variables."
            )

        # Store resolved key privately without exposing it in logs or representations
        self._api_key = resolved_key
        self.model = model or settings.GEMINI_EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION

        logger.info(
            "Initializing EmbeddingService with model: %s, target dimension: %d",
            self.model,
            self.dimension,
        )

        self._client = GoogleGenerativeAIEmbeddings(
            model=self.model,
            google_api_key=self._api_key,
            output_dimensionality=self.dimension,
        )

    def embed_query(self, text: str) -> list[float]:
        """Generate a vector embedding for a single text query.

        Args:
            text: Query string to embed.

        Returns:
            list[float]: Embedding vector of exact target dimension.

        Raises:
            ValueError: If text is empty/whitespace or returned vector has unexpected dimension.
        """
        if not text or not text.strip():
            raise ValueError("Query text cannot be empty or whitespace.")

        vector = self._client.embed_query(text)
        if len(vector) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(vector)}"
            )
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of document strings.

        Args:
            texts: List of document strings to embed.

        Returns:
            list[list[float]]: List of embedding vectors, each of exact target dimension.

        Raises:
            ValueError: If texts list is empty, any text is empty/whitespace,
                        or any returned vector has unexpected dimension.
        """
        if not texts:
            raise ValueError("Document list cannot be empty.")

        for idx, doc in enumerate(texts):
            if not doc or not doc.strip():
                raise ValueError(f"Document at index {idx} cannot be empty or whitespace.")

        vectors = self._client.embed_documents(texts)
        if len(vectors) != len(texts):
            raise ValueError(
                f"Embedding count mismatch: expected {len(texts)} embeddings, got {len(vectors)}"
            )

        for idx, vector in enumerate(vectors):
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Document {idx} embedding dimension mismatch: expected {self.dimension}, got {len(vector)}"
                )
        return vectors
