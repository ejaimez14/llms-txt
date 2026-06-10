#!/bin/bash
set -euo pipefail

BUILD_DIR=".build"
ZIP_FILE="lambda.zip"

rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"

uv export --no-dev --no-hashes -o "$BUILD_DIR/requirements.txt"
# claude-agent-sdk is ECS-only (src/tasks/base.py); 75MB wheel would bloat the zip.
# uv pip install handles cross-platform markers correctly (unlike pip --platform which
# evaluates sys_platform against the host OS rather than the target platform).
grep -v "^claude-agent-sdk" "$BUILD_DIR/requirements.txt" > "$BUILD_DIR/requirements-lambda.txt"
uv pip install -r "$BUILD_DIR/requirements-lambda.txt" \
  --target "$BUILD_DIR" \
  --python-platform linux \
  --python-version 3.11 \
  --no-cache \
  --quiet

cp -r src/ "$BUILD_DIR/src/"

python - <<'EOF'
import zipfile, os, pathlib

build_dir = pathlib.Path(".build")
zip_path  = pathlib.Path("lambda.zip")
exclude   = {".pyc", ".pyo"}
exclude_dirs = {"__pycache__"}

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in build_dir.rglob("*"):
        if path.suffix in exclude:
            continue
        if any(p in exclude_dirs for p in path.parts):
            continue
        if path.name in {"requirements.txt", "requirements-lambda.txt"}:
            continue
        if path.is_file():
            zf.write(path, path.relative_to(build_dir))
EOF

rm -rf "$BUILD_DIR"
echo "Built $ZIP_FILE ($(du -sh $ZIP_FILE | cut -f1))"
