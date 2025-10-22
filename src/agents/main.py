import asyncio
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

from src.tools import journal

# Global env variables
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Resource specific environment variable
s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")
journal_table_name = os.environ.get("JOURNAL_TABLE_NAME", "default-table")
session_id = os.environ.get("SESSION_ID")

# Boto3 configuration constants (using boto3 defaults)
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_MODE = "standard"
DEFAULT_CONNECT_TIMEOUT = 60
DEFAULT_READ_TIMEOUT = 60
DEFAULT_MAX_POOL_CONNECTIONS = 10

# Model configuration constants
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
DEFAULT_REGION = "us-east-1"


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
    model_id: str = DEFAULT_MODEL_ID,
    region_name: str = DEFAULT_REGION,
    boto_config: Optional[BotocoreConfig] = None,
) -> Agent:
    """Create configured Agent instances with proper model setup.

    Args:
        model_id: The Bedrock model ID to use. Defaults to Claude 4 Sonnet.
        region_name: AWS region to use for the Bedrock service.
        boto_config: Optional botocore Config for retry and timeout settings.

    Returns:
        Configured Agent instance with BedrockModel using the provided configuration.
    """
    # Use provided boto_config or create default one
    if boto_config is None:
        boto_config = create_boto_config()

    # Create BedrockModel with boto_client_config
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region_name,
        boto_client_config=boto_config,
    )

    SYSTEM_PROMPT = ""
    SYSTEM_PROMPT += open(os.path.join(os.path.dirname(__file__), "prompt.md")).read()
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{s3_bucket_name}", s3_bucket_name)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{journal_table_name}", journal_table_name)

    # Create agent with configured model
    return Agent(model=bedrock_model, system_prompt=SYSTEM_PROMPT, tools=[use_aws, journal])


# Create agent
agent = create_agent()

# Create BedrockAgentCore app
app = BedrockAgentCoreApp()

# Use the built-in AgentCore logger
logger = app.logger
logger.info("Agent and AgentCore app initialized successfully")


@app.async_task
async def background_agent_task(user_message: str, session_id: str):
    """Background task to process agent request with LLM"""
    logger.info(f"Background task started - Session: {session_id}")

    try:
        # Use Strands native async method - agent will have full LLM interaction
        response = await agent.invoke_async(user_message, session_id=session_id)

        # Log completion with response summary for observability
        logger.info(
            f"Background task completed - Session: {session_id}, Response length: {len(str(response.message)) if hasattr(response, 'message') else 'unknown'}"
        )

        # Return response for proper async task completion (even though no client receives it)
        return response

    except NoCredentialsError:
        logger.error(f"Background task failed - Session: {session_id}: AWS credentials not configured")
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ThrottlingException":
            logger.error(f"Background task failed - Session: {session_id}: LLM throttling")
        elif error_code == "AccessDeniedException":
            logger.error(f"Background task failed - Session: {session_id}: LLM access denied")
        else:
            logger.error(f"Background task failed - Session: {session_id}: AWS error {error_code}")
    except Exception as e:
        logger.error(f"Background task failed - Session: {session_id}: {str(e)}", exc_info=True)


@app.entrypoint
async def invoke(payload):
    """Process user input and return a response - Fire and forget for Lambda.

    Fire-and-forget pattern:
    - Lambda returns immediately (avoiding 15-minute timeout)
    - AgentCore continues processing in background
    - Status automatically becomes HEALTHY_BUSY when background_agent_task() runs
    - Status returns to HEALTHY when background_agent_task() completes
    """
    user_message = payload.get("prompt", "Hello")
    payload_session_id = payload.get("session_id", session_id)

    logger.info(f"Request received - Session: {payload_session_id}")

    try:
        asyncio.create_task(background_agent_task(user_message, payload_session_id))

        logger.info(f"Background processing started - Session: {payload_session_id}")
        return {
            "message": f"Started processing request for session {payload_session_id}. Processing will continue in background.",
            "session_id": payload_session_id,
            "status": "started",
        }
    except Exception as e:
        logger.error(f"Entrypoint error - Session: {payload_session_id}: {str(e)}", exc_info=True)
        return {"error": f"Error starting background processing: {str(e)}", "session_id": payload_session_id}


if __name__ == "__main__":
    app.run()
