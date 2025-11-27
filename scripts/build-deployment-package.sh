#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please run 'make init' first."
    exit 1
fi

echo "Building AgentCore Runtime package..."

mkdir -p build-agents

uv pip compile pyproject.toml --group agents --output-file build-agents/requirements.txt --quiet
uv pip install \
  --target build-agents/ \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  -r build-agents/requirements.txt

cp -r src build-agents/

mkdir -p infra/dist
cd build-agents && zip -qr ../infra/dist/agentcore_runtime.zip . -x "*.pyc" -x "*__pycache__*" -x "requirements.txt" && cd ..

rm -rf build-agents/

echo "✓ Package ready: infra/dist/agentcore_runtime.zip ($(du -h infra/dist/agentcore_runtime.zip | cut -f1))"
