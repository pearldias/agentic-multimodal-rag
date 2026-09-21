import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.services.llm_service import (
    LLMServiceError,
    LLMUnavailableError,
    LLMRateLimitError,
)
from backend.app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
)

rag_service = RAGService()


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="Question to ask the RAG system",
    )
    k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Number of documents to retrieve",
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]
    retrieved_documents: int


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Ask a question using the RAG pipeline.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty or whitespace.",
        )

    try:
        result = rag_service.ask(
            question=request.question,
            k=request.k,
        )

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            sources=result["sources"],
            retrieved_documents=result["retrieved_documents"],
        )

    except ValueError as error:
        logger.warning("Validation error in chat endpoint: %s", error)
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except LLMUnavailableError as error:
        logger.warning("Gemini 503 unavailable: %s", error.message)
        raise HTTPException(
            status_code=503,
            detail=error.message,
        ) from error

    except LLMRateLimitError as error:
        logger.warning("Gemini 429 rate limit: %s", error.message)
        raise HTTPException(
            status_code=429,
            detail=error.message,
        ) from error

    except LLMServiceError as error:
        logger.error("LLMServiceError: %s (status %d)", error.message, error.status_code)
        raise HTTPException(
            status_code=error.status_code,
            detail=error.message,
        ) from error

    except Exception as error:
        logger.exception("Unexpected error during chat processing: %s", error)
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred while processing the question.",
        ) from error