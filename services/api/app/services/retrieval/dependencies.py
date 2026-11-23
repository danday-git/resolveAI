from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.ai_settings import apply
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AppSetting
from app.services.llm import factory


def get_chat_provider(request: Request, db: Session = Depends(get_db)):
    row = db.get(AppSetting, 1)
    if row is None:
        return request.app.state.chat_provider
    return factory.get_chat_provider(apply(row, get_settings()))


def get_embedding_provider(request: Request):
    return request.app.state.embedding_provider
