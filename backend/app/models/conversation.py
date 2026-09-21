"""Pydantic schemas for conversations, messages, and history."""

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """A single stored message in a conversation."""

    id: str
    role: str
    content: str
    sources: list[dict] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    """Summary representation of a conversation for list views."""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(BaseModel):
    """Detailed conversation representation including all messages."""

    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageResponse] = Field(default_factory=list)
