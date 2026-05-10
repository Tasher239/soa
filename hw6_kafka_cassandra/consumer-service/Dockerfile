FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip && pip install \
    "confluent-kafka[avro,schemaregistry]==2.6.1" \
    "fastavro==1.9.7" \
    "cassandra-driver==3.29.2" \
    "fastapi==0.115.4" \
    "uvicorn[standard]==0.32.0" \
    "prometheus-client==0.21.0" \
    "pydantic==2.9.2" \
    "pydantic-settings==2.6.1" \
    "structlog==24.4.0"

COPY pyproject.toml ./
COPY app ./app

EXPOSE 8000
CMD ["python", "-m", "app.main"]
