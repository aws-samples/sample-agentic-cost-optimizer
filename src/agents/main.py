import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, use_aws

from src.shared import EventStatus, record_event
from src.tools import journal, storage

s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")
journal_table_name = os.environ.get("JOURNAL_TABLE_NAME", "default-table")
session_id = os.environ.get("SESSION_ID")
aws_region = os.environ.get("AWS_REGION", "us-east-1")
model_id = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
ttl_days = int(os.environ.get("TTL_DAYS", "90"))

# Required for local development - CDK sets this in deployed environments
if "BYPASS_TOOL_CONSENT" not in os.environ:
    os.environ["BYPASS_TOOL_CONSENT"] = "true"

DEFAULT_MAX_ATTEMPTS = 5  # Increased from default 3 for better resilience with Bedrock
DEFAULT_RETRY_MODE = "standard"  # AWS recommended mode with exponential backoff + jitter
DEFAULT_CONNECT_TIMEOUT = 60  # Bedrock connection establishment typically completes within 10s
DEFAULT_READ_TIMEOUT = 120  # Bedrock streaming responses can take 60-90s for complex queries
DEFAULT_MAX_POOL_CONNECTIONS = 10


def create_boto_config(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    retry_mode: str = DEFAULT_RETRY_MODE,
    connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
    read_timeout: int = DEFAULT_READ_TIMEOUT,
    max_pool_connections: int = DEFAULT_MAX_POOL_CONNECTIONS,
) -> BotocoreConfig:
    """Create botocore Config with retry and timeout settings using boto3 defaults."""
    return BotocoreConfig(
        retries={
            "max_attempts": max_attempts,
            "mode": retry_mode,
        },
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
        max_pool_connections=max_pool_connections,
    )


def create_agent(boto_config: Optional[BotocoreConfig] = None) -> Agent:
    """Create configured Agent instances with proper model setup.

    Uses environment variables for configuration:
    - MODEL_ID: Bedrock model to use
    - AWS_REGION: AWS region for Bedrock service

    Args:
        boto_config: Optional botocore Config for retry and timeout settings.

    Returns:
        Configured Agent instance with BedrockModel using the provided configuration.
    """
    if boto_config is None:
        boto_config = create_boto_config()

    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=aws_region,
        boto_client_config=boto_config,
    )

    current_timestamp = int(time.time())
    current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    SYSTEM_PROMPT = ""
    SYSTEM_PROMPT += open(os.path.join(os.path.dirname(__file__), "prompt.md")).read()
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{s3_bucket_name}", s3_bucket_name)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{journal_table_name}", journal_table_name)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{current_timestamp}", str(current_timestamp))
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{current_datetime}", current_datetime)

    # Note: current_time tool removed - it only returns ISO format which requires parsing
    # Instead, we inject current_timestamp directly into the prompt in Unix format
    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[use_aws, journal, storage, calculator],
    )


# Initialize at module level for Lambda container reuse across invocations
agent = create_agent()
app = BedrockAgentCoreApp()
logger = app.logger
logger.info("Agent and AgentCore app initialized successfully")


# Decorator automatically manages AgentCore status: HEALTHY_BUSY while running, HEALTHY when complete
@app.async_task
async def agent_background_task(user_message: str, session_id: str):
    """Background task to process agent request with LLM"""
    logger.info(f"Background task started - Session: {session_id}")

    try:
        response = await agent.invoke_async(user_message, session_id=session_id)

        logger.info(
            f"Background task completed - Session: {session_id}, Response length: {len(str(response.message)) if hasattr(response, 'message') else 'unknown'}"
        )
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_COMPLETED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )
        return response

    # Return error dicts for structured logging - decorator handles status management
    except NoCredentialsError as e:
        logger.error(f"Background task failed - Session: {session_id}: NoCredentialsError - {str(e)}")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            error_message=f"NoCredentialsError - {str(e)}",
            region_name=aws_region,
        )
        return {
            "error": "NoCredentialsError",
            "error_code": "NoCredentialsError",
            "error_message": str(e),
            "session_id": session_id,
            "status": "failed",
        }

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        error_message = e.response.get("Error", {}).get("Message", "")

        logger.error(f"Background task failed - Session: {session_id}: {error_code} - {error_message}")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            error_message=f"{error_code} - {error_message}",
            region_name=aws_region,
        )
        return {
            "error": "ClientError",
            "error_code": error_code,
            "error_message": error_message,
            "session_id": session_id,
            "status": "failed",
        }

    except Exception as e:
        logger.error(f"Background task failed - Session: {session_id}: {type(e).__name__} - {str(e)}", exc_info=True)
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            error_message=f"{type(e).__name__} - {str(e)}",
            region_name=aws_region,
        )
        return {
            "error": "Exception",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "session_id": session_id,
            "status": "failed",
        }


@app.entrypoint
async def invoke(payload):
    """Process user input and return a response - Fire and forget for Lambda.

    Fire-and-forget pattern:
    - Lambda returns immediately (avoiding 15-minute timeout)
    - AgentCore continues processing in background
    - Status automatically becomes HEALTHY_BUSY when agent_background_task() runs
    - Status returns to HEALTHY when agent_background_task() completes
    """
    user_message = payload.get("prompt", "Hello")
    payload_session_id = payload.get("session_id", session_id)

    logger.info(f"Request received - Session: {payload_session_id}")
    record_event(
        session_id=payload_session_id,
        status=EventStatus.AGENT_INVOKE_STARTED,
        table_name=journal_table_name,
        ttl_days=ttl_days,
        region_name=aws_region,
    )

    try:
        asyncio.create_task(agent_background_task(user_message, payload_session_id))
        logger.info(f"Background processing started - Session: {payload_session_id}")
        record_event(
            session_id=payload_session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_STARTED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            region_name=aws_region,
        )
        return {
            "message": f"Started processing request for session {payload_session_id}. Processing will continue in background.",
            "session_id": payload_session_id,
            "status": "started",
        }
    except Exception as e:
        logger.error(f"Entrypoint error - Session: {payload_session_id}: {str(e)}", exc_info=True)
        record_event(
            session_id=payload_session_id,
            status=EventStatus.AGENT_INVOKE_FAILED,
            table_name=journal_table_name,
            ttl_days=ttl_days,
            error_message=str(e),
            region_name=aws_region,
        )
        return {"error": f"Error starting background processing: {str(e)}", "session_id": payload_session_id}


if __name__ == "__main__":
    app.run()
