#!/bin/bash
set -euo pipefail

BUILD_DIR=".build"
ZIP_FILE="lambda.zip"

rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

uv export --no-dev --no-hashes -o "$BUILD_DIR/requirements.txt"
# claude-agent-sdk is ECS-only; exclude it so it doesn't bloat the Lambda zip.
grep -v "^claude-agent-sdk" "$BUILD_DIR/requirements.txt" > "$BUILD_DIR/requirements-lambda.txt"
uv pip install -r "$BUILD_DIR/requirements-lambda.txt" \
  --target "$BUILD_DIR" \
  --python-platform linux \
  --python-version 3.11 \
  --no-cache \
  --quiet

cp -r src/ "$BUILD_DIR/src/"

cd "$BUILD_DIR"
find . -type f \
  ! -name "*.pyc" \
  ! -name "*.pyo" \
  ! -path "*/__pycache__/*" \
  ! -name "requirements.txt" \
  ! -name "requirements-lambda.txt" \
  | zip -q "../$ZIP_FILE" -@
cd ..

rm -rf "$BUILD_DIR"
echo "Built $ZIP_FILE ($(du -sh $ZIP_FILE | cut -f1))"
