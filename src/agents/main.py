import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, use_aws

from src.shared import EventStatus, get_config, record_event
from src.tools import journal, storage

# Load configuration from environment variables
config = get_config()

# Timestamp values for prompt replacement
current_timestamp = int(time.time())
current_datetime = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

# Required for local development - CDK sets this in deployed environments
if "BYPASS_TOOL_CONSENT" not in os.environ:
    os.environ["BYPASS_TOOL_CONSENT"] = "true"

DEFAULT_MAX_ATTEMPTS = 5  # Increased from default 3 for better resilience with Bedrock
DEFAULT_RETRY_MODE = "standard"  # AWS recommended mode with exponential backoff + jitter
DEFAULT_CONNECT_TIMEOUT = 60  # Time allowed for establishing connection to Bedrock
DEFAULT_READ_TIMEOUT = 600  # Time allowed for streaming responses from model
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


def create_agent(
    system_prompt: str,
    boto_config: Optional[BotocoreConfig] = None,
    tools: Optional[list] = None,
) -> Agent:
    """Create configured Agent instances with proper model setup.

    Uses environment variables for configuration:
    - MODEL_ID: Bedrock model to use
    - AWS_REGION: AWS region for Bedrock service

    Args:
        boto_config: Optional botocore Config for retry and timeout settings.
        system_prompt: System prompt for the agent (required).
        tools: List of tools for the agent (optional).

    Returns:
        Configured Agent instance with BedrockModel using the provided configuration.
    """
    if boto_config is None:
        boto_config = create_boto_config()

    if not system_prompt:
        raise ValueError("system_prompt is required")

    if tools is None:
        tools = []

    bedrock_model = BedrockModel(
        model_id=config.model_id,
        region_name=config.aws_region,
        boto_client_config=boto_config,
    )

    return Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=tools,
    )


REPORT_PROMPT, ANALYSIS_PROMPT = "", ""
# Read prompts
ANALYSIS_PROMPT = open(os.path.join(os.path.dirname(__file__), "analysis_prompt.md")).read()
REPORT_PROMPT = open(os.path.join(os.path.dirname(__file__), "report_prompt.md")).read()

ANALYSIS_PROMPT = ANALYSIS_PROMPT.replace("{current_timestamp}", str(current_timestamp))
ANALYSIS_PROMPT = ANALYSIS_PROMPT.replace("{current_datetime}", current_datetime)


# Initialize at module level for Lambda container reuse across invocations
analysis_agent = create_agent(system_prompt=ANALYSIS_PROMPT, tools=[use_aws, journal, calculator, storage])
report_agent = create_agent(
    system_prompt=REPORT_PROMPT,
    tools=[storage, journal],
)


app = BedrockAgentCoreApp()
logger = app.logger
logger.info("Agent and AgentCore app initialized successfully")


# Decorator automatically manages AgentCore status: HEALTHY_BUSY while running, HEALTHY when complete
@app.async_task
async def background_task(user_message: str, session_id: str):
    """Background task using workflow pattern"""
    logger.info(f"Background task started - Session: {session_id}")

    try:
        await analysis_agent.invoke_async(
            "Analyze AWS costs and identify optimization opportunities",
            session_id=session_id,
        )

        response = await report_agent.invoke_async(
            "Generate cost optimization report based on analysis results",
            session_id=session_id,
        )

        logger.info(f"Background completed - Session: {session_id}")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_COMPLETED,
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            region_name=config.aws_region,
        )
        return response

    # Return error dicts for structured logging - decorator handles status management
    except NoCredentialsError as e:
        logger.error(f"Background task failed - Session: {session_id}: NoCredentialsError - {str(e)}")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            error_message=f"NoCredentialsError - {str(e)}",
            region_name=config.aws_region,
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
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            error_message=f"{error_code} - {error_message}",
            region_name=config.aws_region,
        )
        return {
            "error": "ClientError",
            "error_code": error_code,
            "error_message": error_message,
            "session_id": session_id,
            "status": "failed",
        }

    except Exception as e:
        logger.error(
            f"Background task failed - Session: {session_id}: {type(e).__name__} - {str(e)}",
            exc_info=True,
        )
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            error_message=f"{type(e).__name__} - {str(e)}",
            region_name=config.aws_region,
        )
        return {
            "error": "Exception",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "session_id": session_id,
            "status": "failed",
        }


@app.entrypoint
async def invoke(payload, context: RequestContext):
    """Process user input and return a response - Fire and forget for Lambda.

    Fire-and-forget pattern:
    - Lambda returns immediately (avoiding 15-minute timeout)
    - AgentCore continues processing in background
    - Status automatically becomes HEALTHY_BUSY when background_task() runs
    - Status returns to HEALTHY when background_task() completes
    """
    user_message = payload.get("prompt", "Hello")
    # Get session_id from AgentCore context
    session_id = context.session_id

    logger.info(f"Request received - Session: {session_id}")
    record_event(
        session_id=session_id,
        status=EventStatus.AGENT_RUNTIME_INVOKE_STARTED,
        table_name=config.journal_table_name,
        ttl_days=config.ttl_days,
        region_name=config.aws_region,
    )

    try:
        asyncio.create_task(background_task(user_message, session_id))
        logger.info(f"Background processing started - Session: {session_id}")
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_BACKGROUND_TASK_STARTED,
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            region_name=config.aws_region,
        )
        return {
            "message": f"Started processing request for session {session_id}. Processing will continue in background.",
            "session_id": session_id,
            "status": "started",
        }
    except Exception as e:
        logger.error(f"Entrypoint error - Session: {session_id}: {str(e)}", exc_info=True)
        record_event(
            session_id=session_id,
            status=EventStatus.AGENT_RUNTIME_INVOKE_FAILED,
            table_name=config.journal_table_name,
            ttl_days=config.ttl_days,
            error_message=str(e),
            region_name=config.aws_region,
        )
        return {
            "error": f"Error starting background processing: {str(e)}",
            "session_id": session_id,
        }


if __name__ == "__main__":
    app.run()
