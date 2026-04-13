#!/usr/bin/env bash

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OPENAPI_FILE="$PROJECT_ROOT/openapi/marketplace.yaml"
OUTPUT_DIR="$PROJECT_ROOT/generated"
OUTPUT_FILE="$OUTPUT_DIR/models.py"

mkdir -p "$OUTPUT_DIR"

echo "Generating Pydantic v2 models from $OPENAPI_FILE ..."

datamodel-codegen \
  --input "$OPENAPI_FILE" \
  --input-file-type openapi \
  --output "$OUTPUT_FILE" \
  --output-model-type pydantic_v2.BaseModel \
  --use-annotated \
  --use-field-description \
  --snake-case-field \
  --target-python-version 3.12 \
  --use-default \
  --field-constraints \
  --strict-nullable

touch "$OUTPUT_DIR/__init__.py"
echo "Done -> $OUTPUT_FILE"
