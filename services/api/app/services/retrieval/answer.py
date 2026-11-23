import json
import re
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.limits import check_daily_budget, rate_limit_user
from app.core.logging import request_id_var
from app.core.security_text import detect_injection
from app.core.tokens import approx_tokens
from app.models import Conversation, Message, User
from app.services.llm import prompts
from app.services.llm.base import ChatMessage, ChatProvider, InvalidModelOutput, LLMError
from app.services.llm.usage import record_llm_call
from app.services.retrieval import citations
from app.services.retrieval.retrieve import retrieve


def _parse_response(text: str) -> dict[str, Any]:
    try:
        body = json.loads(text)
    except (ValueError, TypeError):
        raise InvalidModelOutput("Model returned invalid JSON") from None
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("answer"), str)
        or not isinstance(body.get("abstain"), bool)
        or not isinstance(body.get("citations"), list)
    ):
        raise InvalidModelOutput("Model response did not match the expected schema")
    return body


def _call_chat(
    provider: ChatProvider,
    messages: list[ChatMessage],
    owner_id: UUID,
) -> tuple[dict[str, Any], int, int, int, float | None, str, str]:
    last_error: LLMError | None = None
    total_input = total_output = total_latency = 0
    total_cost = 0.0
    cost_unknown = False
    for attempt in range(2):
        try:
            result = provider.chat(
                messages, json_mode=True, max_tokens=get_settings().llm_max_output_tokens
            )
            total_input += result.input_tokens
            total_output += result.output_tokens
            total_latency += result.latency_ms
            cost = record_llm_call(
                operation="chat",
                provider=result.provider,
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_ms=result.latency_ms,
                retries=result.retries,
                prompt_version=prompts.CHAT_PROMPT_VERSION,
                owner_id=owner_id,
            )
            if cost is None:
                cost_unknown = True
            else:
                total_cost += cost
            return (
                _parse_response(result.text),
                total_input,
                total_output,
                total_latency,
                None if cost_unknown else total_cost,
                result.provider,
                result.model,
            )
        except InvalidModelOutput as exc:
            last_error = exc
            if attempt == 1:
                record_llm_call(
                    operation="chat",
                    provider=provider.name,
                    model=provider.model,
                    input_tokens=approx_tokens("\n".join(message.content for message in messages)),
                    latency_ms=total_latency,
                    prompt_version=prompts.CHAT_PROMPT_VERSION,
                    owner_id=owner_id,
                    error_category=exc.category,
                )
        except LLMError as exc:
            record_llm_call(
                operation="chat",
                provider=provider.name,
                model=provider.model,
                input_tokens=approx_tokens("\n".join(message.content for message in messages)),
                latency_ms=total_latency,
                prompt_version=prompts.CHAT_PROMPT_VERSION,
                owner_id=owner_id,
                error_category=exc.category,
            )
            raise
    raise last_error or InvalidModelOutput("Model response did not match the expected schema")


def answer_question(
    request: Request,
    db: Session,
    user: User,
    provider: ChatProvider,
    embedder,
    question: str,
    conversation_id: UUID | None,
    top_k: int,
) -> dict[str, Any]:
    from app.api.deps import get_owned

    rate_limit_user(user.id, request)
    check_daily_budget(db, user)
    if conversation_id:
        conversation = get_owned(db, Conversation, conversation_id, user)
    else:
        conversation = Conversation(owner_id=user.id, title=question[:60])
        db.add(conversation)
        db.flush()
    request_id = request_id_var.get() or str(UUID(int=0))
    try:
        embedded = embedder.embed([question])
    except LLMError as exc:
        record_llm_call(
            operation="embedding",
            provider=embedder.name,
            model=embedder.model,
            owner_id=user.id,
            error_category=exc.category,
        )
        raise
    record_llm_call(
        operation="embedding",
        provider=embedded.provider,
        model=embedded.model,
        input_tokens=embedded.input_tokens,
        latency_ms=embedded.latency_ms,
        retries=embedded.retries,
        owner_id=user.id,
    )
    retrieved = retrieve(db, user.id, question, top_k, embedder, embedded.vectors[0])
    rejected = 0
    citations_out: list[dict[str, Any]] = []
    input_tokens = output_tokens = 0
    provider_name, model_name = provider.name, provider.model
    cost: float | None = 0.0
    if not retrieved:
        answer = prompts.ABSTAIN_MESSAGE
        abstained = True
        retrieval_info = {
            "top_k": top_k,
            "retrieved": [],
            "citations_rejected": 0,
            "prompt_version": prompts.CHAT_PROMPT_VERSION,
        }
        usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "provider": provider_name,
            "model": model_name,
        }
    else:
        flagged = {str(chunk.chunk_id) for chunk in retrieved if detect_injection(chunk.text)}
        message_dicts = prompts.build_chat_messages(question, retrieved, flagged)
        messages = [ChatMessage(**message) for message in message_dicts]
        body, input_tokens, output_tokens, _, cost, provider_name, model_name = _call_chat(
            provider, messages, user.id
        )
        valid, rejected = citations.validate_citations(body["citations"], retrieved)
        abstained = body["abstain"] or not valid
        answer = prompts.ABSTAIN_MESSAGE if abstained else body["answer"]
        if not abstained:
            valid_ids = {item["chunk_id"] for item in valid}
            answer = re.sub(
                r"\[chunk:([^\]]+)\]",
                lambda match: "" if match.group(1) not in valid_ids else match.group(0),
                answer,
            )
            by_id = {str(chunk.chunk_id): chunk for chunk in retrieved}
            citations_out = [
                {
                    **item,
                    "document_id": str(by_id[item["chunk_id"]].document_id),
                    "page": by_id[item["chunk_id"]].page_number,
                    "filename": by_id[item["chunk_id"]].filename,
                }
                for item in valid
            ]
        retrieval_info = {
            "top_k": top_k,
            "retrieved": [
                {
                    "chunk_id": str(chunk.chunk_id),
                    "document_id": str(chunk.document_id),
                    "score": chunk.score,
                }
                for chunk in retrieved
            ],
            "citations_rejected": rejected,
            "prompt_version": prompts.CHAT_PROMPT_VERSION,
        }
        usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": cost,
            "provider": provider_name,
            "model": model_name,
        }
    warnings = [
        match.group(0)
        for pattern in prompts.UNSAFE_OUTPUT_PATTERNS
        for match in pattern.finditer(answer)
    ]
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
        citations_json=[],
        request_id=request_id,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        citations_json=citations_out,
        retrieval_json=retrieval_info,
        request_id=request_id,
    )
    db.add_all([user_message, assistant_message])
    db.commit()
    result = {
        "answer": answer,
        "abstained": abstained,
        "citations": citations_out,
        "conversation_id": str(conversation.id),
        "message_id": str(assistant_message.id),
        "request_id": request_id,
        "usage": usage,
        "retrieval": retrieval_info,
        "safety_warnings": warnings,
    }
    return result
