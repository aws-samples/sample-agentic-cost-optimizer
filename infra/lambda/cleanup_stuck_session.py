"""Lambda function to cleanup stuck AgentCore Runtime sessions"""

import os

import boto3
from aws_lambda_powertools import Logger, Tracer
from botocore.exceptions import ClientError

from src.shared import EventStatus, record_event

logger = Logger()
tracer = Tracer()

bedrock_agentcore = boto3.client("bedrock-agentcore")

agent_runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
if not agent_runtime_arn:
    raise ValueError("AGENT_RUNTIME_ARN environment variable is required")

journal_table_name = os.environ.get("JOURNAL_TABLE_NAME")
if not journal_table_name:
    raise ValueError("JOURNAL_TABLE_NAME environment variable is required")

ttl_days = int(os.environ.get("TTL_DAYS", "90"))
aws_region = os.environ.get("AWS_REGION", "us-east-1")


@tracer.capture_lambda_handler
def lambda_handler(event, context):
    """Lambda handler to cleanup stuck AgentCore Runtime sessions"""
    session_id = event.get("session_id")
    ping_status = event.get("ping_status")

    logger.info("Lambda started", sessionId=session_id, pingStatus=ping_status)

    if not session_id:
        error_msg = "Missing required field: session_id"
        logger.error(error_msg)
        return {"statusCode": 400, "error": error_msg}

    # Check if session is stuck (HealthyBusy when it should be Healthy)
    if ping_status == "HealthyBusy":
        logger.info("Session stuck in HealthyBusy - executing cleanup", sessionId=session_id)

        try:
            # Call stop_runtime_session to cleanup
            response = bedrock_agentcore.stop_runtime_session(
                agentRuntimeId=agent_runtime_arn, runtimeSessionId=session_id
            )

            logger.info(
                "Successfully stopped runtime session",
                sessionId=session_id,
                response=response,
            )

            # Record force stop
            record_event(
                session_id=session_id,
                status=EventStatus.AGENT_RUNTIME_SESSION_FORCE_STOPPED,
                table_name=journal_table_name,
                ttl_days=ttl_days,
                region_name=aws_region,
            )

            return {
                "status": "force_stopped",
                "sessionId": session_id,
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = e.response.get("Error", {}).get("Message", "")
            logger.error(
                "Failed to stop runtime session",
                sessionId=session_id,
                error=error_code,
                errorMessage=error_message,
            )

            # Record force stop failure
            record_event(
                session_id=session_id,
                status=EventStatus.AGENT_RUNTIME_SESSION_FORCE_STOP_FAILED,
                table_name=journal_table_name,
                ttl_days=ttl_days,
                region_name=aws_region,
                error_message=f"Force stop failed: {error_code} - {error_message}",
            )

            raise

    elif ping_status == "Healthy":
        # Session is Healthy - no cleanup needed
        logger.info("Session is Healthy - no cleanup needed", sessionId=session_id)

        # Record that stop was not required
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_RUNTIME_SESSION_STOP_NOT_REQUIRED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )

        return {
            "status": "stop_not_required",
            "sessionId": session_id,
        }

    else:
        # Unexpected ping status - log warning and skip cleanup
        logger.warning(
            "Unexpected ping status - skipping cleanup",
            sessionId=session_id,
            pingStatus=ping_status,
        )

        return {
            "status": "stop_not_required",
            "sessionId": session_id,
            "warning": f"Unexpected ping_status: {ping_status}",
        }
