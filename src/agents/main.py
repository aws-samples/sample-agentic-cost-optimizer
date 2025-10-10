import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands_tools import use_aws

# Import all journaling tools
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from tools import (
    check_journal_table_exists,
    start_session,
    start_task,
    complete_task,
    complete_session,
)

# Global env variables
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Resource specific environment variable
s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")
journal_table_name = os.environ.get("JOURNAL_TABLE_NAME", "default-table")

SYSTEM_PROMPT = ""
SYSTEM_PROMPT += open(os.path.join(os.path.dirname(__file__), "prompt.md")).read()
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{s3_bucket_name}", s3_bucket_name)
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{journal_table_name}", journal_table_name)

# Create an agent with default settings including journaling tools
agent = Agent(
    system_prompt=SYSTEM_PROMPT,
    tools=[
        use_aws,
        check_journal_table_exists,
        start_session,
        start_task,
        complete_task,
        complete_session,
    ],
)

# Create BedrockAgentCore app
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Process user input and return a response"""
    user_message = payload.get("prompt", "Hello")

    # Print the S3 bucket name in the response
    print(f"Processing request with S3 bucket: {s3_bucket_name}")
    # Print DynamoDb table name
    print(f"Processing with journal table: {journal_table_name}")

    # Get response from agent
    response = agent(user_message)

    # Include S3 bucket info in response
    response_with_bucket = f"S3 Bucket: {s3_bucket_name}\n\n{response}"

    return str(response_with_bucket)


if __name__ == "__main__":
    app.run()
