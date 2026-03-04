FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

COPY openapi/ ./openapi/
COPY scripts/ ./scripts/
RUN bash scripts/generate_models.sh

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
