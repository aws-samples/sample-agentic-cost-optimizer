import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

# Read S3_BUCKET_NAME environment variable
s3_bucket_name = os.environ.get("S3_BUCKET_NAME")

# Print the S3 bucket name when the agent starts
if s3_bucket_name:
    print(f"Agent starting with S3 bucket: {s3_bucket_name}")
else:
    print("Agent starting - S3_BUCKET_NAME environment variable not set")

# Create an agent with default settings
agent = Agent()

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
