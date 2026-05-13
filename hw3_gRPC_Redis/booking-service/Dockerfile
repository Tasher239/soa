FROM python:3.12-slim AS base

WORKDIR /app

COPY booking-service/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY proto /proto
RUN mkdir -p app/generated && \
    python -m grpc_tools.protoc \
    -I /proto \
    --python_out=app/generated \
    --grpc_python_out=app/generated \
    /proto/flight.proto && \
    touch app/generated/__init__.py && \
    sed -i 's/^import flight_pb2/from app.generated import flight_pb2/' \
      app/generated/flight_pb2_grpc.py

COPY booking-service/app/ ./app/
COPY booking-service/alembic/ ./alembic/
COPY booking-service/alembic.ini .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
