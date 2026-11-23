from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import check_llm_consent, get_current_user
from app.core.ai_settings import apply
from app.core.config import get_settings
from app.core.database import get_db
from app.models import AppSetting, User
from app.services.llm import factory


def get_chat_provider(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.get(AppSetting, 1)
    if row is None:
        return request.app.state.chat_provider
    settings = apply(row, get_settings())
    # The admin can switch providers between the consent check and this lookup; check again
    # against exactly the provider this request will use.
    check_llm_consent(user, settings)
    return factory.get_chat_provider(settings)


def get_embedding_provider(request: Request):
    return request.app.state.embedding_provider
