#!/bin/bash

# Local development script for running the agent locally
# Fetches S3 bucket and DynamoDB table names from CloudFormation outputs
# Uses your current AWS credentials - the agent will have whatever permissions your credentials have

set -e

# Configuration
STACK_NAME="${STACK_NAME:-InfraStack}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Fetching configuration from CloudFormation stack: $STACK_NAME"
echo "Region: $AWS_REGION"
echo ""

# Fetch CloudFormation outputs
STACK_OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs' \
  --output json)

if [ -z "$STACK_OUTPUTS" ] || [ "$STACK_OUTPUTS" == "null" ]; then
  echo "Error: Could not retrieve stack outputs. Make sure the stack '$STACK_NAME' exists in region '$AWS_REGION'"
  exit 1
fi

# Extract values from outputs
export S3_BUCKET_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AgentDataBucketName") | .OutputValue')
export JOURNAL_TABLE_NAME=$(echo "$STACK_OUTPUTS" | jq -r '.[] | select(.OutputKey=="AgentsTableName") | .OutputValue')

if [ -z "$S3_BUCKET_NAME" ] || [ "$S3_BUCKET_NAME" == "null" ]; then
  echo "Error: Could not find AgentDataBucketName in stack outputs"
  exit 1
fi

if [ -z "$JOURNAL_TABLE_NAME" ] || [ "$JOURNAL_TABLE_NAME" == "null" ]; then
  echo "Error: Could not find AgentsTableName in stack outputs"
  exit 1
fi

# Set environment variables for the agent
export AWS_REGION="$AWS_REGION"
export MODEL_ID="${MODEL_ID:-us.anthropic.claude-sonnet-4-5-20250929-v1:0}"
export TTL_DAYS="${TTL_DAYS:-90}"
export BYPASS_TOOL_CONSENT="true"

echo "Configuration loaded:"
echo "  S3 Bucket: $S3_BUCKET_NAME"
echo "  DynamoDB Table: $JOURNAL_TABLE_NAME"
echo "  AWS Region: $AWS_REGION"
echo "  Model ID: $MODEL_ID"
echo ""
echo "Starting agent with reload on http://localhost:8080/invocations"
echo ""
echo "To test the agent, run this in a new terminal:"
echo "  curl -X POST http://localhost:8080/invocations \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -H 'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: local-dev-\$(uuidgen)' \\"
echo "    -d '{}'"
echo ""

# Run uvicorn directly with reload
uv run uvicorn src.agents.main:app --host 0.0.0.0 --port 8080 --reload
