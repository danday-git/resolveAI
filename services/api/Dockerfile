FROM python:3.12-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/services/api/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock /app/services/api/
RUN pip install --no-cache-dir uv && cd /app/services/api && uv sync --frozen --no-dev
COPY services/api/alembic.ini /app/services/api/alembic.ini
COPY services/api/alembic /app/services/api/alembic
COPY services/api/app /app/services/api/app
COPY evals/fixtures /app/evals/fixtures
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/uploads \
    && chown -R appuser:appuser /app /data/uploads
WORKDIR /app/services/api
USER appuser
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
