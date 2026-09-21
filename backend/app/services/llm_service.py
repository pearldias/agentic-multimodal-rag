import logging
import time
from google import genai
from google.genai import errors

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base exception for LLM service failures."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class LLMUnavailableError(LLMServiceError):
    """Exception raised when Gemini returns 503 / UNAVAILABLE after retries."""

    def __init__(
        self,
        message: str = "The Gemini AI service is temporarily experiencing high demand (503 Service Unavailable). Please try again in a moment.",
    ):
        super().__init__(message, status_code=503)


class LLMRateLimitError(LLMServiceError):
    """Exception raised when Gemini rate limits are hit."""

    def __init__(
        self,
        message: str = "Gemini API rate limit exceeded. Please wait a moment and try again.",
    ):
        super().__init__(message, status_code=429)


class LLMService:
    """Generate grounded answers using Google Gemini."""

    def __init__(
        self,
        model: str | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ):
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not configured")

        self.client = genai.Client(
            api_key=settings.GOOGLE_API_KEY
        )

        self.model = model or settings.GEMINI_LLM_MODEL
        self.max_retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
        self.retry_delay = retry_delay if retry_delay is not None else settings.LLM_RETRY_DELAY

    def generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using only the retrieved context."""

        if not question.strip():
            raise ValueError("Question cannot be empty")

        if not context.strip():
            return "I could not find relevant information in the documents."

        prompt = f"""
You are a helpful enterprise document assistant.

Answer the user's question using only the provided context.

Rules:
1. Do not use outside knowledge.
2. If the context does not contain the answer, say:
   "I could not find this information in the provided documents."
3. Do not invent facts.
4. Give a clear and concise answer.
5. Include source references such as [Source 1] or [Source 2]
   wherever appropriate.

User Question:
{question}

Retrieved Context:
{context}

Answer:
"""

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                return response.text or "No answer was generated."

            except errors.ServerError as e:
                is_503 = (
                    getattr(e, "code", None) == 503
                    or "503" in str(e)
                    or "UNAVAILABLE" in str(e)
                )
                if is_503:
                    logger.warning(
                        "Gemini 503 UNAVAILABLE on attempt %d/%d for model %s. Retrying...",
                        attempt,
                        self.max_retries,
                        self.model,
                    )
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * attempt)
                        continue
                    raise LLMUnavailableError(
                        "The Gemini AI service is temporarily experiencing high demand (503 Service Unavailable). Please try again in a moment."
                    ) from e

                logger.error("Gemini ServerError (status %s)", getattr(e, "code", "unknown"))
                raise LLMServiceError(
                    "The AI service encountered a server error. Please try again later.",
                    status_code=502,
                ) from e

            except errors.ClientError as e:
                logger.error("Gemini ClientError (status %s)", getattr(e, "code", "unknown"))
                if getattr(e, "code", None) == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    raise LLMRateLimitError(
                        "Gemini API rate limit exceeded. Please wait a moment and try again."
                    ) from e
                raise LLMServiceError(
                    "The AI service request could not be processed.",
                    status_code=400 if getattr(e, "code", None) == 400 else 502,
                ) from e

            except errors.APIError as e:
                logger.error("Gemini APIError (status %s)", getattr(e, "code", "unknown"))
                if getattr(e, "code", None) == 503 or "503" in str(e) or "UNAVAILABLE" in str(e):
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * attempt)
                        continue
                    raise LLMUnavailableError(
                        "The Gemini AI service is temporarily experiencing high demand (503 Service Unavailable). Please try again in a moment."
                    ) from e
                raise LLMServiceError("The AI service encountered an error.", status_code=502) from e

            except Exception as e:
                logger.error("Unexpected error during Gemini generation: %s", type(e).__name__)
                raise LLMServiceError("Unexpected error during text generation.", status_code=500) from e

        raise LLMUnavailableError(
            "The Gemini AI service is temporarily experiencing high demand (503 Service Unavailable). Please try again in a moment."
        )