import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.services.conversation_service import ConversationService
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
conversation_service = ConversationService()


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="Question to ask the RAG system",
    )
    k: int = Field(
        default=settings.RERANK_TOP_K,
        ge=1,
        le=10,
        description="Number of documents to retrieve",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Optional ID of an existing conversation",
    )


class ChatResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str
    sources: list[dict]
    retrieved_documents: int


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Ask a question using the RAG pipeline with short-term memory and persistence.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty or whitespace.",
        )

    # Resolve or create conversation session
    conv_id = request.conversation_id
    if not conv_id:
        title = conversation_service.generate_title_from_question(request.question)
        conv = conversation_service.create_conversation(title=title)
        conv_id = conv.id
    else:
        existing = conversation_service.get_conversation(conv_id)
        if not existing:
            title = conversation_service.generate_title_from_question(request.question)
            conv = conversation_service.create_conversation(
                title=title,
                conversation_id=conv_id,
            )
            conv_id = conv.id

    try:
        try:
            result = rag_service.ask(
                question=request.question,
                k=request.k,
                conversation_id=conv_id,
            )
        except TypeError as type_err:
            if "conversation_id" in str(type_err):
                result = rag_service.ask(
                    question=request.question,
                    k=request.k,
                )
            else:
                raise

        # Persist messages upon successful generation
        conversation_service.add_message(
            conversation_id=conv_id,
            role="user",
            content=request.question.strip(),
        )
        conversation_service.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=result["answer"],
            sources=result["sources"],
        )

        return ChatResponse(
            conversation_id=conv_id,
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


@router.post("/stream")
def chat_stream(request: ChatRequest):
    """
    Stream question answering using RAG pipeline, Cohere reranking, and Gemini streaming.
    Yields Server-Sent Events (SSE) and persists conversation messages upon completion.
    """
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty or whitespace.",
        )

    # Resolve or create conversation session
    conv_id = request.conversation_id
    if not conv_id:
        title = conversation_service.generate_title_from_question(request.question)
        conv = conversation_service.create_conversation(title=title)
        conv_id = conv.id
    else:
        existing = conversation_service.get_conversation(conv_id)
        if not existing:
            title = conversation_service.generate_title_from_question(request.question)
            conv = conversation_service.create_conversation(
                title=title,
                conversation_id=conv_id,
            )
            conv_id = conv.id

    def event_generator():
        try:
            metadata, token_stream = rag_service.ask_stream(
                question=request.question,
                k=request.k,
                conversation_id=conv_id,
            )

            # Send initial metadata event with sources and search info
            meta_payload = {
                "type": "metadata",
                "conversation_id": conv_id,
                "question": request.question,
                "sources": metadata["sources"],
                "retrieved_documents": metadata["retrieved_documents"],
                "search_query": metadata["search_query"],
            }
            yield f"data: {json.dumps(meta_payload)}\n\n"

            accumulated_answer = []
            for token in token_stream:
                accumulated_answer.append(token)
                token_payload = {
                    "type": "token",
                    "content": token,
                }
                yield f"data: {json.dumps(token_payload)}\n\n"

            full_answer = "".join(accumulated_answer).strip() or "No answer was generated."

            # Persist user & assistant messages upon completion
            conversation_service.add_message(
                conversation_id=conv_id,
                role="user",
                content=request.question.strip(),
            )
            conversation_service.add_message(
                conversation_id=conv_id,
                role="assistant",
                content=full_answer,
                sources=metadata["sources"],
            )

            # Send done event
            done_payload = {
                "type": "done",
                "conversation_id": conv_id,
                "answer": full_answer,
                "sources": metadata["sources"],
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except LLMUnavailableError as error:
            logger.warning("Gemini 503 unavailable during stream: %s", error.message)
            err_payload = {
                "type": "error",
                "error": error.message,
                "status_code": 503,
            }
            yield f"data: {json.dumps(err_payload)}\n\n"

        except LLMRateLimitError as error:
            logger.warning("Gemini 429 rate limit during stream: %s", error.message)
            err_payload = {
                "type": "error",
                "error": error.message,
                "status_code": 429,
            }
            yield f"data: {json.dumps(err_payload)}\n\n"

        except LLMServiceError as error:
            logger.error("LLMServiceError during stream: %s", error.message)
            err_payload = {
                "type": "error",
                "error": error.message,
                "status_code": error.status_code,
            }
            yield f"data: {json.dumps(err_payload)}\n\n"

        except Exception as error:
            logger.exception("Unexpected error during streaming chat: %s", error)
            err_payload = {
                "type": "error",
                "error": "An internal server error occurred while processing the question.",
                "status_code": 500,
            }
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )