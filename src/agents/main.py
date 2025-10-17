import logging
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

from src.tools import journal

# Configure logging with reasonable output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.info("Agent module loaded successfully")

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


# Create an agent
logger.info("Creating agent with environment variables:")
logger.info(f"  S3_BUCKET_NAME: {s3_bucket_name}")
logger.info(f"  JOURNAL_TABLE_NAME: {journal_table_name}")
logger.info(f"  SESSION_ID: {session_id}")
logger.info(f"  AWS_REGION: {os.environ.get('AWS_REGION', 'not set')}")

agent = create_agent()
logger.info("Agent created successfully")

# Create BedrockAgentCore app
app = BedrockAgentCoreApp()
logger.info("BedrockAgentCore app initialized")


def background_agent_processing(user_message: str, session_id: str, task_id: str):
    """Background function to process agent request with progress tracking"""
    logger.info(f"--> Starting cost optimization analysis - Task: {task_id}, Session: {session_id}")
    logger.info(f"--> User request: '{user_message}'")

    try:
        logger.info("--> Initializing agent processing...")
        response = agent(user_message, session_id=session_id)
        logger.info(f"--> Cost optimization analysis completed - Task: {task_id}")
        logger.info(f"--> Final response length: {len(str(response))} characters")

        app.complete_async_task(task_id)
        return str(response)

    except NoCredentialsError:
        error_msg = "AWS credentials are not configured. Please set up your AWS credentials."
        logger.error(f"--> Credentials error - Task: {task_id}: {error_msg}")
        app.complete_async_task(task_id)
        return error_msg
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ThrottlingException":
            error_msg = "I'm currently experiencing high demand. Please try again in a moment."
        elif error_code == "AccessDeniedException":
            error_msg = "I don't have the necessary permissions to access the model."
        else:
            error_msg = "I'm experiencing some technical difficulties. Please try again later."

        logger.error(f"--> AWS error - Task: {task_id}, Code: {error_code}: {error_msg}")
        app.complete_async_task(task_id)
        return error_msg
    except Exception as e:
        error_msg = "I encountered an unexpected error. Please try again."
        logger.error(f"--> Unexpected error - Task: {task_id}: {str(e)}", exc_info=True)
        app.complete_async_task(task_id)
        return error_msg


@app.entrypoint
def invoke(payload):
    """Process user input and return a response"""
    user_message = payload.get("prompt", "Hello")
    payload_session_id = payload.get("session_id", session_id)

    logger.info(f"--> AgentCore invocation - Session: {payload_session_id}, Message: '{user_message}'")

    try:
        # Start tracking the async task manually (this sets status to HealthyBusy)
        task_id = app.add_async_task("cost_analysis", {"session_id": payload_session_id, "message": user_message})
        logger.info(f"--> Created async task: {task_id}")

        # Start background work in a separate thread
        import threading

        thread = threading.Thread(
            target=background_agent_processing,
            args=(user_message, payload_session_id, task_id),
            daemon=True,
            name=f"AgentTask-{task_id}",
        )
        thread.start()

        logger.info(f"--> Background analysis started - Task: {task_id}")

        # Return immediately to client (AgentCore connection closes here)
        return f"Started cost optimization analysis for session {payload_session_id}. Processing will continue in background."
    except Exception as e:
        logger.error(f"--> Failed to start background task: {str(e)}", exc_info=True)
        return f"Error starting background processing: {str(e)}"


if __name__ == "__main__":
    app.run()
