# Sample Agentic Cost Optimizer

> **Note**: This is a sample project and work in progress. Use it as a reference for building AI agents with AWS Bedrock Agent Core.

An AI agent that analyzes your AWS Lambda functions and generates cost optimization reports. It discovers Lambda resources, collects metrics, identifies savings opportunities, and produces detailed recommendations.

## What It Does

The agent runs a two-phase workflow:

1. **Analysis Phase**: Discovers Lambda functions, collects CloudWatch metrics and logs, analyzes memory usage and invocation patterns, identifies optimization opportunities
2. **Report Phase**: Generates a cost optimization report with specific recommendations, estimated savings, implementation steps, and supporting evidence

Results are saved to S3 and tracked in DynamoDB for audit trails.

## How It Works

- **Agent Runtime**: Python agent using Strands framework and AWS Bedrock models
- **Orchestration**: Step Functions workflow triggered by EventBridge (scheduled or manual)
- **Storage**: S3 for reports, DynamoDB for event journaling
- **Infrastructure**: AWS CDK (TypeScript) for deployment

## Architecture

![Architecture Diagram](docs/Agentic%20Cost%20Optimization.png)

The diagram shows the agent workflow with 4 tools:

- **use_aws tool**: Collects cost data, Lambda logs, and Lambda configurations from your AWS account
- **calculator tool**: Performs time range calculations and cost computations
- **storage tool**: Saves analysis results and final reports to S3
- **journal tool**: Records workflow events to DynamoDB for audit trails

The **Analysis Agent** uses all 4 tools to discover resources and analyze costs. The **Report Agent** uses storage and journal tools to generate reports. **Bedrock** provides the AI model powering both agents.

## Prerequisites

Install these tools:

```bash
brew install python uv node aws-cli docker
npm install -g aws-cdk
```

Configure AWS credentials:

```bash
aws configure
```

## Quick Start

1. **Install dependencies**:
   ```bash
   make setup
   ```

2. **Deploy to AWS** (first time only):
   ```bash
   make cdk-bootstrap
   ```

3. **Deploy the stack**:
   ```bash
   make cdk-deploy
   ```

4. **Trigger the agent**:
   ```bash
   make trigger-workflow
   ```

The agent will analyze your Lambda functions and save a cost optimization report to S3.

## Local Testing

Run the agent locally:

```bash
make run
```

In another terminal, send a request:

```bash
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze costs"}'
```

## Project Structure

```
.
├── src/
│   ├── agents/          # Agent code and prompts
│   ├── tools/           # Custom tools (journal, storage)
│   └── shared/          # Shared utilities
├── infra/               # CDK infrastructure (TypeScript)
│   ├── lib/             # Stack definitions
│   └── lambda/          # Lambda function handlers
├── tests/               # Test files
└── Makefile             # Common commands
```

## Configuration

Set these environment variables (or use defaults):

- `ENVIRONMENT`: Environment name (default: `dev`)
- `VERSION`: Version tag (default: `v1`)
- `MODEL_ID`: Bedrock model ID (default: Claude Sonnet 4.5)
- `TTL_DAYS`: DynamoDB record retention (default: `90`)

## Deployment

Deploy changes:

```bash
make cdk-deploy          # Full deployment
make cdk-hotswap         # Fast Lambda-only updates
make cdk-watch           # Auto-deploy on file changes
```

## Triggering the Agent

**Scheduled**: Runs daily at 6am UTC (configured in EventBridge)

**Manual**: Trigger anytime:

```bash
make trigger-workflow
```

**Custom trigger**:

```bash
aws events put-events --entries '[{
  "Source": "manual-trigger",
  "DetailType": "execute-agent",
  "Detail": "{}"
}]'
```

## Monitoring

Check the Step Functions console for workflow execution status. View reports in the S3 bucket (output in CDK deployment). Query DynamoDB for event history and audit trails.

## Testing

Run tests:

```bash
make test                # All tests
make check               # Linting and formatting
```

## Cleanup

Remove AWS resources:

```bash
make cdk-destroy
```

Remove local artifacts:

```bash
make clean
```

## Development

See [Local Development Guide](docs/LOCAL_DEVELOPMENT.md) for detailed setup and development workflow.

## Common Issues

**Agent fails to start**: Check AWS credentials are configured and have necessary permissions (Lambda, CloudWatch, S3, DynamoDB, Bedrock).

**No Lambda functions found**: The agent analyzes Lambda functions in `us-east-1`. Ensure you have functions in that region or modify the region in the code.

**Deployment fails**: Run `make cdk-bootstrap` first if this is your first CDK deployment in the account/region.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for security issue reporting.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

