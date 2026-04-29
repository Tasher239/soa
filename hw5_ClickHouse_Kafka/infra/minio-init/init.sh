#!/bin/sh
set -eu

MC_ALIAS="${MC_ALIAS:-local}"
MINIO_URL="${MINIO_URL:-http://minio:9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
BUCKET="${BUCKET:-movie-analytics}"

echo "[minio-init] waiting for MinIO at $MINIO_URL..."
until mc alias set "$MC_ALIAS" "$MINIO_URL" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  sleep 2
done

echo "[minio-init] ensuring bucket $BUCKET exists..."
mc mb --ignore-existing "$MC_ALIAS/$BUCKET"

# Keep the container alive briefly so compose marks it completed cleanly
echo "[minio-init] done."
