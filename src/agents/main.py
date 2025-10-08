import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands_tools import use_aws

# Global env variables
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Resource specific environment variable
s3_bucket_name = os.environ.get("S3_BUCKET_NAME", "default-bucket")

SYSTEM_PROMPT = ""
SYSTEM_PROMPT += open("src/agents/prompt.md").read()
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{s3_bucket_name}", s3_bucket_name)

# Create an agent with default settings
agent = Agent(system_prompt=SYSTEM_PROMPT, tools=[use_aws])

# Create BedrockAgentCore app
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    """Process user input and return a response"""
    user_message = payload.get("prompt", "Hello")

    # Print the S3 bucket name in the response
    print(f"Processing request with S3 bucket: {s3_bucket_name}")

    # Get response from agent
    response = agent(user_message)

    # Include S3 bucket info in response
    response_with_bucket = f"S3 Bucket: {s3_bucket_name}\n\n{response}"

    return str(response_with_bucket)


if __name__ == "__main__":
    app.run()
