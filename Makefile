export UV_PROJECT_ENVIRONMENT := .venv

.PHONY: help setup init pre-commit-install check test run-agent-local invoke-agent-local cdk-bootstrap cdk-deploy cdk-hotswap cdk-watch cdk-destroy trigger-workflow clean

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
	@echo "Agent Evaluations:"
	@echo "  make eval AGENT=<name>  - Run agent E2E eval (e.g., analysis)"
	@echo ""
	@echo "Local Development:"
	@echo "  make run-agent-local   - Run agent locally with reload"
	@echo "  make invoke-agent-local - Invoke local agent (run in separate terminal)"
	@echo ""
	@echo "AWS Deployment:"
	@echo "  make cdk-bootstrap - Bootstrap CDK (run once per AWS account/region)"
	@echo "  make cdk-deploy   - Deploy CDK stack to AWS"
	@echo "  make cdk-hotswap  - Fast deploy Lambda changes only"
	@echo "  make cdk-watch    - Watch for changes and auto-deploy"
	@echo "  make cdk-destroy  - Destroy CDK stack from AWS"
	@echo "  make trigger-workflow - Trigger Step Function workflow via EventBridge"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove venv and build artifacts"

setup: init pre-commit-install
	@echo "✓ Project setup complete!"

init:
	uv sync --group agents --group dev --group eval
	cd infra && npm install
	@echo "✓ Python deps installed in .venv/"
	@echo "✓ Node deps installed in infra/"

pre-commit-install:
	GIT_CONFIG=/dev/null uv run pre-commit install
	@echo "✓ Pre-commit hooks installed"

check:
	uv run pre-commit run --all-files

test:
	@echo "Running Python tests with coverage..."
	uv run pytest tests/ --cov=src --cov-report=term-missing
	@echo "Running TypeScript tests..."
	cd infra && npm test
	@echo "✓ All tests completed!"

eval:
ifdef AGENT
	@echo "Running $(AGENT) agent evaluation..."
	uv run pytest evals/test_$(AGENT).py -v -s
else
	@echo "Usage: make eval AGENT=<agent_name>"
	@echo ""
	@echo "Available agents:"
	@echo "  analysis     - Analysis agent (~3 min)"
	@echo ""
	@echo "Example: make eval AGENT=analysis"
endif

run-agent-local:
	./scripts/run-agent-locally.sh

invoke-agent-local:
	@echo "Invoking local agent..."
	@curl -X POST http://localhost:8080/invocations \
		-H 'Content-Type: application/json' \
		-H 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-dev-'$$(uuidgen) \
		-d '{}'


cdk-bootstrap: 
	@echo "Bootstrapping CDK..."
	cd infra && npm run build && npx cdk bootstrap
	@echo "✓ CDK bootstrap completed"

cdk-deploy:
	@echo "Deploying CDK stack..."
	@echo "Environment: $(or $(ENVIRONMENT),dev), Version: $(or $(VERSION),v1)"
	npm run deploy --prefix infra
	@echo "✓ CDK deployment completed"

cdk-hotswap: 
	@echo "Fast deploying Lambda changes..."
	@echo "Environment: $(or $(ENVIRONMENT),dev), Version: $(or $(VERSION),v1)"
	npx cdk deploy --hotswap --prefix infra
	@echo "✓ CDK hotswap deployment completed"

cdk-watch: 
	@echo "Starting CDK watch mode..."
	@echo "Environment: $(or $(ENVIRONMENT),dev), Version: $(or $(VERSION),v1)"
	npx cdk watch --prefix infra

cdk-destroy: 
	@echo "Destroying CDK stack..."
	npm run destroy --prefix infra
	@echo "✓ CDK stack destroyed"

trigger-workflow:
	@echo "Triggering Step Function workflow via EventBridge..."
	AWS_PAGER="" aws events put-events --entries '[{"Source": "manual-trigger", "DetailType": "execute-agent", "Detail": "{}"}]'
	@echo "✓ Workflow triggered successfully"

clean:
	rm -rf .venv .pytest_cache __pycache__ */__pycache__ *.pyc .ruff_cache .build dist
	rm -rf infra/node_modules infra/cdk.out infra/dist
	@echo "Cleaned."
