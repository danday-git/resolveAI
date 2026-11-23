from fastapi import Request


def get_chat_provider(request: Request):
    return request.app.state.chat_provider


def get_embedding_provider(request: Request):
    return request.app.state.embedding_provider
