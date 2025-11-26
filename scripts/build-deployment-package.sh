#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please run 'make init' first."
    exit 1
fi

echo "Building AgentCore Runtime package..."

mkdir -p build

uv pip compile pyproject.toml --group agents --output-file build/requirements.txt --quiet
uv pip install \
  --target build/ \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  -r build/requirements.txt

cp -r src build/

mkdir -p infra/dist
cd build && zip -qr ../infra/dist/agentcore_runtime.zip . -x "*.pyc" -x "*__pycache__*" -x "requirements.txt" && cd ..

rm -rf build/

echo "✓ Package ready: infra/dist/agentcore_runtime.zip ($(du -h infra/dist/agentcore_runtime.zip | cut -f1))"
