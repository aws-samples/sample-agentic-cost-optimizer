# Local Development Setup

## Prerequisites

Install these tools on macOS:

```bash
brew install python uv node aws-cli docker
npm install -g aws-cdk
```

- **python**: Python 3.12+ runtime
- **uv**: Python package manager and virtual environment tool
- **node**: Required for CDK infrastructure
- **aws-cli**: AWS command line interface
- **docker**: Container runtime for building images
- **aws-cdk**: CDK CLI tool for infrastructure deployment

## Setup

1. **Configure AWS credentials**:
   ```bash
   aws configure
   ```

2. **Install dependencies and setup project**:
   ```bash
   make setup
   ```
   This installs Python deps in `.venv/`, Node deps in `infra/`, and sets up pre-commit hooks.

## Development Workflow

- **Run local agent**: `make run`
- **Format and lint code**: `make check`
- **Build Docker image**: `make docker-build`
- **Trigger Step Function workflow**: `make trigger-workflow`

## AWS Deployment

First-time setup (run once per AWS account/region):
```bash
make cdk-bootstrap
```

Deploy to AWS:
```bash
make cdk-deploy      # Full deployment
make cdk-hotswap     # Fast Lambda-only updates
make cdk-watch       # Auto-deploy on changes
```

Cleanup:
```bash
make cdk-destroy     # Remove AWS resources
make clean           # Remove local build artifacts
```

## Adding Dependencies

**Python dependencies** (add to `pyproject.toml`):
- Agent dependencies: Add to `[dependency-groups.agents]`
- Development tools: Add to `[dependency-groups.dev]`

**Node dependencies** (add to `infra/package.json`):
- Add to `dependencies` or `devDependencies` as appropriate

After adding any dependencies, run:
```bash
make init
```

## Testing

**Note**: The agent requires AWS credentials. For local execution, your configured AWS profile is used automatically. For Docker, pass credentials as environment variables.

**Test locally**:
```bash
# Option 1: Direct execution (uses local AWS profile)
make run
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!"}'

# Option 2: Docker container (requires AWS credentials)
make docker-build
docker run --platform linux/arm64 -p 8080:8080 \
  -e S3_BUCKET_NAME=your-bucket \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
  -e AWS_REGION="$AWS_REGION" \
  strands-agent
curl -X POST http://localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Hello!"}'
```

**Test in AWS**:
```bash
# Direct BedrockAgentCore invocation
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "RUNTIME_ARN_FROM_CDK_OUTPUT" \
  --payload "$(echo '{"prompt": "Hello!"}' | base64)" \
  response.json

# Lambda invocation
aws lambda invoke \
  --function-name "LAMBDA_NAME" \
  --payload "$(echo '{"session_id": "test-session", "prompt": "Hello!"}' | base64)" \
  response.json
```

## Step Function Workflow Testing

Test the complete agent orchestration flow including Step Function workflow and status monitoring:

```bash
# Trigger workflow via EventBridge (simplest method)
make trigger-workflow

# Or trigger manually with custom details
aws events put-events --entries '[
  {
    "Source": "manual-trigger", 
    "DetailType": "execute-agent",
    "Detail": "{\"description\": \"Test workflow execution\"}"
  }
]'
```

**How it works**:
- EventBridge generates a unique event ID that becomes the `session_id`
- The Step Function orchestrates agent invocation and status monitoring
- Monitor execution progress via AWS Console (Step Functions and DynamoDB)

## Project Structure

- `src/agents/` - Python agent code
- `src/tools/` - Agent tools (journal, etc.)
- `infra/` - CDK infrastructure (TypeScript)
- `infra/lambda/` - Lambda function code
- `tests/` - Python test files
- `requirements/` - Generated Python requirements files
- `.venv/` - Python virtual environment (auto-created)

Run `make help` for all available commands.