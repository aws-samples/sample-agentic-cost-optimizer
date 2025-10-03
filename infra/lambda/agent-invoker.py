import json
import os

import boto3


def lambda_handler(event, context):
    """Lambda function to invoke Agent Core runtime"""

    # Log S3 bucket name
    s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
    print(f"S3 Bucket: {s3_bucket_name}")

    # Get runtime ARN from environment
    agent_arn = os.environ.get("AGENT_CORE_RUNTIME_ARN")

    # Extract message from event
    prompt = event.get("message", "Tell me a joke")
    print(f"Invoking agent with prompt: {prompt}")

    # Initialize the AgentCore client
    agent_core_client = boto3.client("bedrock-agentcore")

    try:
        # Prepare the payload
        payload = json.dumps({"prompt": prompt}).encode()

        # Invoke the agent
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, payload=payload
        )

        # Process streaming response
        content = []
        for chunk in response.get("response", []):
            content.append(chunk.decode("utf-8"))

        agent_response = json.loads("".join(content))
        print(f"Agent response: {agent_response}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Success",
                    "agentResponse": agent_response,
                    "s3Bucket": s3_bucket_name,
                }
            ),
        }

    except Exception as e:
        print(f"Error invoking agent: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "s3Bucket": s3_bucket_name}),
        }
