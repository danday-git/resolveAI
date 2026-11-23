from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ApiError
from app.models import Conversation, Message, User
from app.services.llm.base import ChatProvider
from app.services.retrieval.answer import answer_question
from app.services.retrieval.dependencies import get_chat_provider, get_embedding_provider

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=10)


@router.post("/chat")
def chat(
    body: ChatRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[ChatProvider, Depends(get_chat_provider)],
    embedder=Depends(get_embedding_provider),
):
    return answer_question(
        request,
        db,
        user,
        provider,
        embedder,
        body.question,
        body.conversation_id,
        body.top_k or get_settings().retrieval_top_k,
    )


@router.get("/conversations")
def list_conversations(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not 1 <= limit <= 100 or offset < 0:
        raise ApiError(422, "VALIDATION_ERROR", "limit must be 1..100 and offset non-negative")
    condition = Conversation.owner_id == user.id
    items = db.scalars(
        select(Conversation)
        .where(condition)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    total = db.scalar(select(func.count()).select_from(Conversation).where(condition))
    return {
        "items": [
            {"id": str(item.id), "title": item.title, "created_at": item.created_at}
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation = get_owned(db, Conversation, conversation_id, user)
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    ).all()
    return {
        "items": [
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "citations": message.citations_json,
                "retrieval": message.retrieval_json,
                "request_id": message.request_id,
                "created_at": message.created_at,
            }
            for message in messages
        ]
    }
