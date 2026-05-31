FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/shared /opt/cinema-shared
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org /opt/cinema-shared

COPY tests/pyproject.toml ./
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .

COPY tests/ ./tests/

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
