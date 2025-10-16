import logging
import os
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import ClientError, NoCredentialsError
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global env variables
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Resource specific environment variable
s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")

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
    SYSTEM_PROMPT += open("src/agents/prompt.md").read()
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{s3_bucket_name}", s3_bucket_name)

    # Create agent with configured model
    return Agent(model=bedrock_model, system_prompt=SYSTEM_PROMPT, tools=[use_aws])


# Create an agent
agent = create_agent()

# Create BedrockAgentCore app
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Process user input and return a response"""
    user_message = payload.get("prompt", "Hello")

    try:
        response = agent(user_message)
        return str(response)
    except NoCredentialsError as e:
        logger.error(f"AWS credentials not found: {str(e)}")
        return "AWS credentials are not configured. Please set up your AWS credentials."
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"Bedrock error [{error_code}]: {str(e)}")

        # Handle common Bedrock model invocation errors
        if error_code == "ThrottlingException":
            return "I'm currently experiencing high demand. Please try again in a moment."
        elif error_code == "AccessDeniedException":
            return "I don't have the necessary permissions to access the model."
        else:
            return "I'm experiencing some technical difficulties. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return "I encountered an unexpected error. Please try again."


if __name__ == "__main__":
    app.run()
