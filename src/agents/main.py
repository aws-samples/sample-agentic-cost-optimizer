import asyncio
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, use_aws

from src.shared import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_POOL_CONNECTIONS,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RETRY_MODE,
    EventStatus,
    record_event,
)
from src.shared.config import config
from src.tools import convert_time_unix_to_iso, current_time_unix_utc, journal, storage

app = BedrockAgentCoreApp()
logger = app.logger
logger.info("Agent and AgentCore app initialized successfully")


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


def load_prompts() -> tuple[str, str]:
    """Load analysis and report prompts from markdown files.

    Returns:
        tuple[str, str]: (analysis_prompt, report_prompt)
    """
    prompt_dir = os.path.dirname(__file__)

    with open(os.path.join(prompt_dir, "analysis_prompt.md"), encoding="utf-8") as f:
        analysis_prompt = f.read()

    with open(os.path.join(prompt_dir, "report_prompt.md"), encoding="utf-8") as f:
        report_prompt = f.read()

    return analysis_prompt, report_prompt


def _handle_background_task_error(
    session_id: str,
    exception: Exception,
) -> dict:
    """Centralized error handling for background task failures.

    Args:
        session_id: The session ID for the workflow
        exception: The exception that was raised

    Returns:
        Standardized error dictionary for structured logging
    """
    # Determine error type and extract details
    if isinstance(exception, NoCredentialsError):
        error_type = "NoCredentialsError"
        error_code = "NoCredentialsError"
        error_message = str(exception)
        exc_info = False
    elif isinstance(exception, ClientError):
        error_type = "ClientError"
        error_code = exception.response.get("Error", {}).get("Code", "")
        error_message = exception.response.get("Error", {}).get("Message", "")
        exc_info = False
    else:
        error_type = "Exception"
        error_code = None
        error_message = str(exception)
        exc_info = True

    logger.error(
        f"Background task failed - Session: {session_id}: {error_type} - {error_message}",
        exc_info=exc_info,
    )

    record_event(
        session_id=session_id,
        status=EventStatus.AGENT_BACKGROUND_TASK_FAILED,
        table_name=config.journal_table_name,
        ttl_days=config.ttl_days,
        error_message=f"{error_type} - {error_message}",
        region_name=config.aws_region,
    )

    # Build response
    error_dict = {
        "error": error_type,
        "error_message": error_message,
        "session_id": session_id,
        "status": "failed",
    }

    if error_code:
        error_dict["error_code"] = error_code
    if error_type == "Exception":
        error_dict["error_type"] = type(exception).__name__

    return error_dict


# Decorator automatically manages AgentCore status: HEALTHY_BUSY while running, HEALTHY when complete
@app.async_task
async def background_task(user_message: str, session_id: str):
    """Background task using workflow pattern."""
    logger.info(f"Background task started - Session: {session_id}")

    analysis_prompt, report_prompt = load_prompts()

    analysis_agent = create_agent(
        system_prompt=analysis_prompt,
        tools=[use_aws, journal, calculator, storage, current_time_unix_utc, convert_time_unix_to_iso],
    )
    report_agent = create_agent(
        system_prompt=report_prompt,
        tools=[storage, journal],
    )

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

    except NoCredentialsError as e:
        return _handle_background_task_error(session_id, e)

    except ClientError as e:
        return _handle_background_task_error(session_id, e)

    except Exception as e:
        return _handle_background_task_error(session_id, e)


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
