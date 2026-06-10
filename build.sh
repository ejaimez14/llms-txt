#!/bin/bash
set -euo pipefail

BUILD_DIR=".build"
ZIP_FILE="lambda.zip"

rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

# pip --platform selects wheels but evaluates environment markers against the host
# interpreter, so Windows-only deps (pywin32, via mcp) resolve as required on a Windows
# build host yet have no manylinux wheel. The uv export is a fully-resolved closure, so
# drop win32-only lines and install with --no-deps: pip installs exactly the pinned set
# without re-resolving mcp's metadata (which would re-add pywin32). Host-OS agnostic.
uv export --no-dev --no-hashes \
  | grep -ivE "(sys_platform *== *'win32')|(platform_system *== *'Windows')" \
  > "$BUILD_DIR/requirements.txt"
pip install -r "$BUILD_DIR/requirements.txt" -t "$BUILD_DIR" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 311 \
  --abi cp311 \
  --only-binary=:all: \
  --no-deps \
  --quiet

cp -r src/ "$BUILD_DIR/src/"

cd "$BUILD_DIR"
zip -r "../$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*" -x "requirements.txt"
cd ..

rm -rf "$BUILD_DIR"
echo "Built $ZIP_FILE ($(du -sh $ZIP_FILE | cut -f1))"
