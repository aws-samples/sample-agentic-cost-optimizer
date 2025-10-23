export UV_PROJECT_ENVIRONMENT := .venv
REQ_DIR := requirements
DOCKER_IMAGE_NAME := strands-agent
DOCKER_TAG := latest

.PHONY: help setup init pre-commit-install check test run docker-build cdk-bootstrap cdk-deploy cdk-hotswap cdk-watch cdk-destroy clean

help:
	@echo "Development Workflow:"
	@echo "  make setup        - Complete project setup (init + pre-commit)"
	@echo "  make init         - Install Python and Node dependencies"
	@echo "  make pre-commit-install - Install pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  make check        - Run all code quality checks (pre-commit)"
	@echo "  make test         - Run all tests"
	@echo ""
	@echo "Development:"
	@echo "  make run          - Run the sample local agent"
	@echo "  make trigger-workflow - Trigger Step Function workflow via EventBridge"
	@echo "  make docker-build - Build Docker image for agent"
	@echo ""
	@echo "AWS Deployment:"
	@echo "  make cdk-bootstrap - Bootstrap CDK (run once per AWS account/region)"
	@echo "  make cdk-deploy   - Deploy CDK stack to AWS"
	@echo "  make cdk-hotswap  - Fast deploy Lambda changes only"
	@echo "  make cdk-watch    - Watch for changes and auto-deploy"
	@echo "  make cdk-destroy  - Destroy CDK stack from AWS"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove venv and build artifacts"

setup: init pre-commit-install
	@echo "✓ Project setup complete!"

init:
	@mkdir -p $(REQ_DIR)
	uv sync --group agents --group dev
	uv export --format requirements-txt --no-dev \
	  --group agents \
	  -o $(REQ_DIR)/agents.txt
	cd infra && npm install
	@echo "✓ Python deps installed in .venv/"
	@echo "✓ Exported $(REQ_DIR)/agents.txt"
	@echo "✓ Node deps installed in infra/"

pre-commit-install:
	GIT_CONFIG=/dev/null uv run pre-commit install
	@echo "✓ Pre-commit hooks installed"

check:
	uv run pre-commit run --all-files

test:
	@echo "Running Python tests..."
	uv run pytest tests/ -v
	@echo "Running TypeScript tests..."
	cd infra && npm test
	@echo "✓ All tests completed!"

run:
	PYTHONPATH=src uv run python -m agents.main

docker-build: 
	@echo "Building Docker image: $(DOCKER_IMAGE_NAME):$(DOCKER_TAG)"
	docker buildx build --platform linux/arm64 -t $(DOCKER_IMAGE_NAME):$(DOCKER_TAG) --load .
	@echo "✓ Docker image built successfully"

cdk-bootstrap: 
	@echo "Bootstrapping CDK..."
	cd infra && npm run build && npx cdk bootstrap
	@echo "✓ CDK bootstrap completed"

cdk-deploy: 
	@echo "Deploying CDK stack..."
	cd infra && npm run build && npm run deploy:dev
	@echo "✓ CDK deployment completed"

cdk-hotswap: 
	@echo "Fast deploying Lambda changes..."
	cd infra && npm run build && npx cdk deploy --hotswap --context env=dev
	@echo "✓ CDK hotswap deployment completed"

cdk-watch: 
	@echo "Starting CDK watch mode..."
	cd infra && npm run build && npx cdk watch --context env=dev

cdk-destroy: 
	@echo "Destroying CDK stack..."
	cd infra && npm run destroy:dev
	@echo "✓ CDK stack destroyed"

trigger-workflow:
	@echo "Triggering Step Function workflow via EventBridge..."
	AWS_PAGER="" aws events put-events --entries '[{"Source": "manual-trigger", "DetailType": "execute-agent", "Detail": "{}"}]'
	@echo "✓ Workflow triggered successfully"

clean:
	rm -rf .venv .pytest_cache __pycache__ */__pycache__ *.pyc .ruff_cache requirements .build dist
	rm -rf infra/node_modules infra/cdk.out infra/dist
	@echo "Cleaned."
