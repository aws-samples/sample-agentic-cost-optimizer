"""Lambda function to invoke Bedrock AgentCore runtime"""

import json
import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.shared.functions import get_tracer_id

from src.shared import EventStatus, record_event

logger = Logger()
tracer = Tracer()

bedrock_agentcore = boto3.client("bedrock-agentcore")

# Environment variables
agent_runtime_arn = os.environ.get("AGENT_CORE_RUNTIME_ARN")
if not agent_runtime_arn:
    raise ValueError("AGENT_CORE_RUNTIME_ARN environment variable is required")

journal_table_name = os.environ.get("JOURNAL_TABLE_NAME")
if not journal_table_name:
    raise ValueError("JOURNAL_TABLE_NAME environment variable is required")

ttl_days = int(os.environ.get("TTL_DAYS", "30"))
aws_region = os.environ.get("AWS_REGION", "us-east-1")


@tracer.capture_lambda_handler
def handler(event, context):
    """Lambda handler to invoke Bedrock AgentCore runtime"""
    session_id = event["session_id"]

    logger.info("Lambda started", sessionId=session_id)

    try:
        logger.info("Calling AgentCore...")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_INVOCATION_STARTED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )

        # Get X-Ray trace ID for GenAI Observability (using Powertools utility)
        trace_id = get_tracer_id()

        # Invoke AgentCore runtime
        # Note: Empty payload is intentional - session_id is in the context
        # into the context by AgentCore and accessed via context.session_id
        invoke_params = {
            "agentRuntimeArn": agent_runtime_arn,
            "runtimeSessionId": session_id,
            "payload": json.dumps({}),
        }

        # Links Lambda X-Ray traces with AgentCore for end-to-end observability in GenAI console
        if trace_id:
            invoke_params["traceId"] = trace_id

        response = bedrock_agentcore.invoke_agent_runtime(**invoke_params)

        logger.info(
            "AgentCore responded",
            sessionId=response.get("runtimeSessionId"),
            status=response.get("statusCode"),
        )

        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_INVOCATION_SUCCEEDED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )

        return {
            "status": response.get("statusCode"),
            "sessionId": response.get("runtimeSessionId"),
        }

    except Exception as e:
        logger.error("AgentCore failed", error=str(e), sessionId=session_id)
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_INVOCATION_FAILED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            error_message=str(e),
            region_name=aws_region,
        )
        raise
