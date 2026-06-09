#!/bin/bash
set -euo pipefail

BUILD_DIR=".build"
ZIP_FILE="lambda.zip"

rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

uv export --no-dev --no-hashes -o "$BUILD_DIR/requirements.txt"
pip install -r "$BUILD_DIR/requirements.txt" -t "$BUILD_DIR" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 311 \
  --abi cp311 \
  --only-binary=:all: \
  --quiet

cp -r src/ "$BUILD_DIR/src/"

cd "$BUILD_DIR"
zip -r "../$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*" -x "requirements.txt"
cd ..

rm -rf "$BUILD_DIR"
echo "Built $ZIP_FILE ($(du -sh $ZIP_FILE | cut -f1))"
