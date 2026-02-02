#!/bin/bash
set -e

cd "$(dirname "$0")/.."

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed. Please run 'make init' first."
    exit 1
fi

echo "Building AgentCore Runtime package..."

mkdir -p infra/dist/build-agent

# Export from lockfile to ensure consistent versions between local dev and deployment
uv export --group agents --no-hashes --output-file infra/dist/build-agent/requirements.txt --quiet
uv pip install \
  --target infra/dist/build-agent/ \
  --python-version 3.12 \
  --python-platform aarch64-manylinux2014 \
  --only-binary :all: \
  -r infra/dist/build-agent/requirements.txt

cp -r src infra/dist/build-agent/

cd infra/dist/build-agent && zip -qr ../agentcore_runtime.zip . -x "*.pyc" -x "*__pycache__*" -x "requirements.txt" && cd ../../..

echo "✓ Package ready: infra/dist/agentcore_runtime.zip ($(du -h infra/dist/agentcore_runtime.zip | cut -f1))"
