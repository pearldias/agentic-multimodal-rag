"""API endpoints for managing persistent conversations and history."""

import logging
from fastapi import APIRouter, HTTPException

from backend.app.models.conversation import (
    ConversationDetail,
    ConversationSummary,
)
from backend.app.services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/conversations",
    tags=["Conversations"],
)

conversation_service = ConversationService()


@router.get("", response_model=list[ConversationSummary])
def list_conversations(limit: int = 50):
    """Retrieve list of past conversations ordered by most recently updated."""
    try:
        return conversation_service.list_conversations(limit=limit)
    except Exception as error:
        logger.exception("Failed to list conversations: %s", error)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve conversation history.",
        ) from error


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str):
    """Retrieve a conversation and its messages by ID."""
    try:
        conversation = conversation_service.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found.",
            )
        return conversation
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to get conversation %s: %s", conversation_id, error)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve conversation details.",
        ) from error


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages."""
    try:
        deleted = conversation_service.delete_conversation(conversation_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation '{conversation_id}' not found.",
            )
        return {"status": "deleted", "id": conversation_id}
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Failed to delete conversation %s: %s", conversation_id, error)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete conversation.",
        ) from error
